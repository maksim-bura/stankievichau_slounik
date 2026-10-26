"""Scan a codebase and produce a cleanup plan skeleton plus raw metrics.

Run: py -3 tools/plan_cleanup.py [--root DIR] [--scenario thorough|quick]
     py -3 tools/plan_cleanup.py --since HEAD~1 --quick

The generated markdown is a starting point: delete irrelevant findings, then work
through the checklist. Thresholds are overridable with --config JSON.
"""
import argparse
import ast
import json
import re
import subprocess
import sys
import tempfile
import time
from collections import Counter, defaultdict
from pathlib import Path

DEFAULT_EXCLUDE = {
    '.git', '.hg', '.svn', '__pycache__', '.mypy_cache', '.pytest_cache',
    '.venv', 'venv', 'node_modules', 'build', 'dist', '.idea', '.vscode',
}
DEFAULT_CONFIG = {
    'max_file_lines': 500,
    'max_func_lines': 40,
    'max_line_length': 99,
    'literal_min_length': 14,
    'literal_min_count': 3,
    'bucket_pattern': r'_?(utils|helpers?)$',
}

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', default='.')
    parser.add_argument('--scenario', choices=('thorough', 'quick'), default='thorough')
    parser.add_argument('--since', default='HEAD~1')
    parser.add_argument('--config', default=None)
    parser.add_argument('--out', default=None)
    parser.add_argument('--exclude', default='')
    return parser.parse_args()


def load_config(path):
    config = dict(DEFAULT_CONFIG)
    if path:
        config.update(json.loads(Path(path).read_text(encoding='utf-8')))
    return config


def changed_files(root, since):
    result = subprocess.run(
        ['git', 'diff', '--name-only', '--diff-filter=ACMR', since],
        cwd=str(root), capture_output=True, text=True)
    if result.returncode != 0:
        print('git diff failed: %s' % result.stderr.strip())
        return set()
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def iter_py(root, excluded):
    for path in sorted(root.rglob('*.py')):
        if excluded & set(path.relative_to(root).parts):
            continue
        yield path


def function_lengths(tree):
    found = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            end = getattr(node, 'end_lineno', node.lineno)
            found.append((node.name, node.lineno, end - node.lineno + 1))
    return found


def docstring_nodes(tree):
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                             ast.AsyncFunctionDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) \
                    and isinstance(first.value.value, str):
                found.add(id(first.value))
    return found


def literal_counts(trees, config):
    counts = Counter()
    locations = defaultdict(list)
    for path, tree, skip in trees:
        for node in ast.walk(tree):
            if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
                continue
            if id(node) in skip:
                continue
            value = node.value
            if len(value.strip()) < config['literal_min_length']:
                continue
            if '\n' in value.strip():
                continue
            counts[value] += 1
            locations[value].append('%s:%d' % (path, node.lineno))
    return {
        value: locations[value]
        for value, count in counts.items()
        if count >= config['literal_min_count']
    }


def scan(root, paths, config):
    metrics = []
    trees = []
    private_imports = []
    for path in paths:
        relative = path.relative_to(root).as_posix()
        text = path.read_text(encoding='utf-8')
        lines = text.splitlines()
        try:
            tree = ast.parse(text)
        except SyntaxError as exc:
            metrics.append({'path': relative, 'lines': len(lines),
                            'max_line': max((len(l) for l in lines), default=0),
                            'functions': [], 'error': str(exc)})
            continue
        skip = docstring_nodes(tree)
        trees.append((relative, tree, skip))
        functions = function_lengths(tree)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                source = '.' * node.level + node.module
                for alias in node.names:
                    if alias.name.startswith('_') and not alias.name.startswith('__'):
                        private_imports.append('%s:%d imports %s from %s' % (
                            relative, node.lineno, alias.name, source))
        metrics.append({
            'path': relative,
            'lines': len(lines),
            'max_line': max((len(line) for line in lines), default=0),
            'functions': functions,
            'error': None,
        })
    return metrics, trees, private_imports


def folder_findings(root, paths):
    by_folder = defaultdict(list)
    for path in paths:
        by_folder[path.parent].append(path)
    one_module = []
    duplicated = []
    for folder, files in by_folder.items():
        modules = [f for f in files if f.name != '__init__.py']
        relative = folder.relative_to(root).as_posix()
        if len(modules) == 1 and folder != root:
            one_module.append('%s (%s)' % (relative, modules[0].name))
        for module in modules:
            if module.stem == folder.name:
                duplicated.append(relative + '/' + module.name)
    return one_module, duplicated


def bucket_modules(metrics, pattern):
    regex = re.compile(pattern)
    return [m['path'] for m in metrics if regex.search(Path(m['path']).stem)]


def render(root, scenario, config, metrics, findings, folders):
    lines = [
        '# Cleanup plan — %s' % root,
        '',
        'Generated %s, scenario: **%s**' % (time.strftime('%Y-%m-%d %H:%M'), scenario),
        'Thresholds: files > %d lines, functions > %d lines, lines > %d chars, '
        'repeated strings >= %d chars x%d' % (
            config['max_file_lines'], config['max_func_lines'],
            config['max_line_length'], config['literal_min_length'],
            config['literal_min_count']),
        '',
        '## Scope',
        '',
        '- files scanned: %d (%d lines)' % (
            len(metrics), sum(m['lines'] for m in metrics)),
        '- NEXT: confirm with the user — thorough (whole codebase) or quick '
        '(changed files only), and whether behavior changes are allowed '
        '(tools/DEVELOPMENT_PRACTICES.md §8.11)',
        '- NEXT: keep a verification baseline before touching anything',
        '',
    ]

    def block(title, items, hint=None):
        lines.append('### %s (%d)' % (title, len(items)))
        lines.append('')
        if hint:
            lines.append(hint)
            lines.append('')
        for item in items[:60]:
            lines.append('- %s' % item)
        if len(items) > 60:
            lines.append('- ... %d more' % (len(items) - 60))
        lines.append('')

    block('Long files', findings['long_files'],
          'Split by entity, not by line count: a 900-line single widget stays whole.')
    block('Long functions', findings['long_functions'],
          'Extract one owner per rule; never pass `self` state across modules.')
    block('Long lines', findings['long_lines'])
    block('Bucket modules (_utils/_helpers/_helper)', findings['buckets'],
          'A module that does something gets a verb name; one that holds data gets a noun.')
    block('Private cross-module imports', findings['private_imports'],
          'Make the name public in its owner, or move the rule.')
    block('One-module folders', folders['one_module'],
          'A folder is a layer with >= 2 modules; otherwise fold it back.')
    block('Folder/file name duplication', folders['duplicated'])
    block('Repeated string literals', findings['literals'],
          'Promote to a single named constant in the owner module.')

    lines.append('## Checklist')
    lines.append('')
    lines.append('- [ ] scope + scenario confirmed with the user')
    lines.append('- [ ] baseline captured (DB rows / expected probe output)')
    lines.append('- [ ] dead code removed, one owner per rule')
    lines.append('- [ ] renames/moves applied through tools/rewrite_imports.py')
    lines.append('- [ ] behavior changes: consent recorded before editing')
    lines.append('- [ ] tools/check_cleanup.py green')
    lines.append('- [ ] docs updated, temp files removed, diff reviewed')
    lines.append('')
    lines.append('## Raw counts')
    lines.append('')
    lines.append('- files: %d' % len(metrics))
    lines.append('- long files: %d' % len(findings['long_files']))
    lines.append('- long functions: %d' % len(findings['long_functions']))
    lines.append('- long lines: %d' % len(findings['long_lines']))
    lines.append('- private imports: %d' % len(findings['private_imports']))
    lines.append('- repeated literals: %d' % len(findings['literals']))
    return '\n'.join(lines)


def main():
    args = parse_args()
    root = Path(args.root).resolve()
    config = load_config(args.config)
    excluded = set(DEFAULT_EXCLUDE)
    excluded.update(item.strip() for item in args.exclude.split(',') if item.strip())
    paths = list(iter_py(root, excluded))
    if args.scenario == 'quick':
        changed = changed_files(root, args.since)
        paths = [path for path in paths
                 if path.relative_to(root).as_posix() in changed]
    metrics, trees, private_imports = scan(root, paths, config)
    literals = literal_counts(trees, config)
    one_module, duplicated = folder_findings(root, paths)
    findings = {
        'long_files': ['%s (%d lines)' % (m['path'], m['lines'])
                       for m in metrics if m['lines'] > config['max_file_lines']],
        'long_functions': ['%s:%d %s (%d lines)' % (m['path'], start, name, length)
                           for m in metrics for name, start, length in m['functions']
                           if length > config['max_func_lines']],
        'long_lines': ['%s:%d (%d chars)' % (m['path'], number, len(line))
                       for m in metrics
                       for number, line in enumerate(
                           (root / m['path']).read_text(encoding='utf-8').splitlines(), 1)
                       if len(line) > config['max_line_length']],
        'buckets': bucket_modules(metrics, config['bucket_pattern']),
        'private_imports': private_imports,
        'literals': ['%r x%d %s' % (value, len(locations), ', '.join(locations[:4]))
                     for value, locations in sorted(
                         literals.items(), key=lambda item: -len(item[1]))],
    }
    text = render(root, args.scenario, config, metrics, findings,
                  {'one_module': one_module, 'duplicated': duplicated})
    out = Path(args.out).resolve() if args.out else (
        Path(tempfile.gettempdir()) / 'cleanup' / root.name / 'plan.md')
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding='utf-8')
    print('scenario: %s' % args.scenario)
    print('files: %d' % len(metrics))
    print('findings: files %d | functions %d | lines %d | buckets %d | '
          'private %d | literals %d | one-module folders %d | name dupes %d' % (
              len(findings['long_files']), len(findings['long_functions']),
              len(findings['long_lines']), len(findings['buckets']),
              len(findings['private_imports']), len(findings['literals']),
              len(one_module), len(duplicated)))
    print('plan: %s' % out)
    if not paths:
        print('WARNING: no files matched (quick mode needs changed files)')
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
