"""Build a fast-to-read map, snapshot, and symbol index of a codebase.

Run: py -3 tools/read_codebase.py [--root DIR] [--out DIR] [--ext .py,.md]
     py -3 tools/read_codebase.py --query 'def on_link_clicked'

Outputs (into --out, default %TEMP%/cleanup/<root name>):
  code_map.txt       per-file outline: size, imports, classes, functions with line ranges
  code_snapshot.txt  every file with line numbers, ready to grep visually
  symbols.txt        name -> path:line -> kind
"""
import argparse
import ast
import re
import sys
import tempfile
import time
from pathlib import Path

DEFAULT_EXCLUDE = {
    '.git', '.hg', '.svn', '__pycache__', '.mypy_cache', '.pytest_cache',
    '.venv', 'venv', 'env', 'node_modules', 'build', 'dist', '.idea',
    '.vscode', 'site-packages',
}


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', default='.')
    parser.add_argument('--out', default=None)
    parser.add_argument('--ext', default='.py')
    parser.add_argument('--exclude', default='')
    parser.add_argument('--query', default=None)
    parser.add_argument('--context', type=int, default=3)
    parser.add_argument('--limit', type=int, default=200)
    return parser.parse_args()


def iter_files(root, extensions, excluded):
    for path in sorted(root.rglob('*')):
        if not path.is_file():
            continue
        if path.suffix.lower() not in extensions:
            continue
        if set(path.relative_to(root).parts) & excluded:
            continue
        yield path


def count_lines(text):
    return text.count('\n') + (0 if text.endswith('\n') else 1)


def outline_python(path, text):
    entries = []
    imports = 0
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        return entries, imports, 'PARSE ERROR: %s' % exc
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            imports += 1
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            entries.append(('class', node.name, node.lineno,
                            getattr(node, 'end_lineno', node.lineno)))
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    entries.append(('  method', child.name, child.lineno,
                                    getattr(child, 'end_lineno', child.lineno)))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            entries.append(('def', node.name, node.lineno,
                            getattr(node, 'end_lineno', node.lineno)))
    return entries, imports, None


def outline_text(text):
    entries = []
    for number, line in enumerate(text.splitlines(), 1):
        match = re.match(r'^(#{1,4})\s+(.*)$', line)
        if match:
            entries.append(('h%d' % len(match.group(1)), match.group(2).strip(),
                            number, number))
    return entries, 0, None


def render_map(root, files, details):
    lines = ['# code map: %s (%s)' % (root, time.strftime('%Y-%m-%d %H:%M')),
             '# files: %d, total lines: %d' % (
                 len(details), sum(d['lines'] for d in details)), '']
    for detail in details:
        lines.append('%s  (%d lines, max %d, imports %d)' % (
            detail['path'], detail['lines'], detail['max_line'], detail['imports']))
        if detail['error']:
            lines.append('  ! %s' % detail['error'])
        for kind, name, start, end in detail['entries']:
            lines.append('  %-7s %-46s %d-%d (%d)' % (
                kind, name, start, end, end - start + 1))
        lines.append('')
    return '\n'.join(lines)


def main():
    args = parse_args()
    root = Path(args.root).resolve()
    extensions = {item.strip().lower() if item.strip().startswith('.')
                  else '.' + item.strip().lower()
                  for item in args.ext.split(',') if item.strip()}
    excluded = set(DEFAULT_EXCLUDE)
    excluded.update(item.strip() for item in args.exclude.split(',') if item.strip())
    out = Path(args.out).resolve() if args.out else (
        Path(tempfile.gettempdir()) / 'cleanup' / root.name)
    out.mkdir(parents=True, exist_ok=True)

    files = list(iter_files(root, extensions, excluded))
    details = []
    snapshot = []
    symbols = []
    for path in files:
        relative = path.relative_to(root).as_posix()
        try:
            text = path.read_text(encoding='utf-8')
        except (UnicodeDecodeError, OSError) as exc:
            details.append({'path': relative, 'lines': 0, 'max_line': 0,
                            'imports': 0, 'entries': [], 'error': str(exc)})
            continue
        if path.suffix.lower() == '.py':
            entries, imports, error = outline_python(path, text)
        else:
            entries, imports, error = outline_text(text)
        lines = count_lines(text)
        details.append({
            'path': relative,
            'lines': lines,
            'max_line': max((len(line) for line in text.splitlines()), default=0),
            'imports': imports,
            'entries': entries,
            'error': error,
        })
        for kind, name, start, end in entries:
            symbols.append('%s\t%s:%d\t%s' % (name, relative, start, kind.strip()))
        snapshot.append('=' * 78)
        snapshot.append('===== %s (%d lines) =====' % (relative, lines))
        snapshot.append('=' * 78)
        for number, line in enumerate(text.splitlines(), 1):
            snapshot.append('%5d| %s' % (number, line))
        snapshot.append('')

    (out / 'code_map.txt').write_text(render_map(root, files, details), encoding='utf-8')
    (out / 'code_snapshot.txt').write_text('\n'.join(snapshot), encoding='utf-8')
    (out / 'symbols.txt').write_text('\n'.join(sorted(symbols)), encoding='utf-8')
    print('files: %d' % len(details))
    print('map:      %s' % (out / 'code_map.txt'))
    print('snapshot: %s' % (out / 'code_snapshot.txt'))
    print('symbols:  %s' % (out / 'symbols.txt'))

    if args.query:
        pattern = re.compile(args.query)
        snapshot_lines = '\n'.join(snapshot).splitlines()
        hits = 0
        for index, line in enumerate(snapshot_lines):
            if not pattern.search(line):
                continue
            hits += 1
            start = max(0, index - args.context)
            end = min(len(snapshot_lines), index + args.context + 1)
            for current in range(start, end):
                print(snapshot_lines[current])
            print('-' * 40)
            if hits >= args.limit:
                print('stopped at %d hits' % args.limit)
                break
        return 0 if hits else 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
