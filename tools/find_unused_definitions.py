"""Report module-level definitions that nothing in the tree references.

Run: py -3 tools/find_unused_definitions.py [--root DIR] [--ext .py]
     py -3 tools/find_unused_definitions.py --kinds def,class,constant
     py -3 tools/find_unused_definitions.py --ignore '^main$'

Complements find_unused_imports.py: this covers functions and classes, not
imports. The scan is name-based, so getattr/string dispatch and dynamic exports
are invisible; treat hits as candidates, not proof. Names in __all__, dunders,
and __init__.py are skipped. Exits 1 when a candidate is found.
"""
import argparse
import ast
import io
import re
import sys
import tokenize
from collections import Counter
from pathlib import Path

DEFAULT_EXCLUDE = {
    '.git', '.hg', '.svn', '__pycache__', '.mypy_cache', '.pytest_cache',
    '.venv', 'venv', 'env', 'node_modules', 'build', 'dist', '.idea',
    '.vscode', 'site-packages',
}


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', default='.')
    parser.add_argument('--ext', default='.py')
    parser.add_argument('--exclude', default='')
    parser.add_argument('--kinds', default='def,class')
    parser.add_argument('--ignore', action='append', default=[])
    parser.add_argument('--show-used', action='store_true')
    return parser.parse_args()


def iter_files(root, extensions, excluded):
    for path in sorted(root.rglob('*')):
        if not path.is_file():
            continue
        if path.suffix.lower() not in extensions:
            continue
        if excluded & set(path.relative_to(root).parts):
            continue
        yield path


def definitions(tree, kinds):
    found = []
    for node in tree.body:
        if 'def' in kinds and isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            found.append(('def', node.name, node.lineno))
        elif 'class' in kinds and isinstance(node, ast.ClassDef):
            found.append(('class', node.name, node.lineno))
        elif 'constant' in kinds and isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    found.append(('constant', target.id, node.lineno))
    return found


def exported_names(tree):
    names = set()
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(target, ast.Name) and target.id == '__all__'
                   for target in node.targets):
            continue
        try:
            value = ast.literal_eval(node.value)
        except (ValueError, SyntaxError):
            continue
        if isinstance(value, (list, tuple)):
            names.update(item for item in value if isinstance(item, str))
    return names


def count_names(text):
    counts = Counter()
    try:
        for token in tokenize.generate_tokens(io.StringIO(text).readline):
            if token.type == tokenize.NAME:
                counts[token.string] += 1
        return counts
    except (tokenize.TokenError, SyntaxError):
        return None


def count_names_by_ast(tree):
    counts = Counter()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            counts[node.id] += 1
        elif isinstance(node, ast.Attribute):
            counts[node.attr] += 1
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            counts[node.name] += 1
    return counts


def main():
    args = parse_args()
    root = Path(args.root).resolve()
    extensions = {item.strip().lower() if item.strip().startswith('.')
                  else '.' + item.strip().lower()
                  for item in args.ext.split(',') if item.strip()}
    excluded = set(DEFAULT_EXCLUDE)
    excluded.update(item.strip() for item in args.exclude.split(',') if item.strip())
    kinds = {item.strip() for item in args.kinds.split(',') if item.strip()}
    ignored = [re.compile(item) for item in args.ignore]

    paths = list(iter_files(root, extensions, excluded))
    total = Counter()
    candidates = []
    declared = Counter()

    for path in paths:
        relative = path.relative_to(root).as_posix()
        try:
            text = path.read_text(encoding='utf-8')
            tree = ast.parse(text)
        except (SyntaxError, UnicodeDecodeError) as exc:
            print('%s: PARSE %s' % (relative, exc))
            continue
        counts = count_names(text)
        total.update(counts if counts is not None else count_names_by_ast(tree))
        if path.name == '__init__.py':
            continue
        exported = exported_names(tree)
        for kind, name, line in definitions(tree, kinds):
            if name.startswith('__') and name.endswith('__'):
                continue
            if name in exported:
                continue
            if any(pattern.search(name) for pattern in ignored):
                continue
            declared[name] += 1
            candidates.append((relative, line, kind, name))

    findings = [(relative, line, kind, name) for relative, line, kind, name in candidates
                if total.get(name, 0) <= declared[name]]
    for relative, line, kind, name in sorted(findings):
        print('%s:%d: unused %s %s' % (relative, line, kind, name))
    if args.show_used:
        for relative, line, kind, name in sorted(set(candidates) - set(findings)):
            print('%s:%d: used %s %s' % (relative, line, kind, name))
    print('unused definitions: %d (of %d scanned)' % (len(findings), len(candidates)))
    return 1 if findings else 0


if __name__ == '__main__':
    sys.exit(main())
