"""Delete comments from source files (the project rule is: no comments in code).

Run: py -3 tools/strip_comments.py [--root DIR] [--ext .py] [--exclude parts]
     py -3 tools/strip_comments.py --dry-run
     py -3 tools/strip_comments.py --allow '^# type:'

Tokenizes each file, so a '#' inside a string is not a comment and docstrings are
untouched. Shebangs, coding cookies, and --allow matches are kept. Line endings
and the source encoding are preserved, and the write is refused when the ast
tree would change. Exits 1 only when a file cannot be read, parsed, or safely
rewritten.
"""
import argparse
import ast
import re
import sys
import tokenize
from pathlib import Path

DEFAULT_EXCLUDE = {
    '.git', '.hg', '.svn', '__pycache__', '.mypy_cache', '.pytest_cache',
    '.venv', 'venv', 'env', 'node_modules', 'build', 'dist', '.idea',
    '.vscode', 'site-packages',
}
MAX_TEXT = 160


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', default='.')
    parser.add_argument('--ext', default='.py')
    parser.add_argument('--exclude', default='')
    parser.add_argument('--allow', action='append', default=[])
    parser.add_argument('--dry-run', action='store_true')
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


def is_preamble(text, line):
    if line > 2:
        return False
    if line == 1 and text.startswith('#!'):
        return True
    return bool(re.match(r'^#.*coding[:=]', text))


def read_source(path):
    with open(path, 'rb') as handle:
        encoding, _ = tokenize.detect_encoding(handle.readline)
    with open(path, 'r', encoding=encoding, newline='') as handle:
        return handle.read(), encoding


def comment_spans(text, allowed):
    lines = text.splitlines(keepends=True)
    found = []
    tokens = tokenize.generate_tokens(iter(lines).__next__)
    for token in tokens:
        if token.type != tokenize.COMMENT:
            continue
        comment = token.string
        if is_preamble(comment, token.start[0]):
            continue
        if any(pattern.search(comment) for pattern in allowed):
            continue
        found.append((token.start[0], token.start[1], comment))
    return found


def strip_spans(text, spans):
    lines = text.splitlines(keepends=True)
    drop = set()
    cut = {}
    for row, column, _comment in spans:
        if not lines[row - 1][:column].strip():
            drop.add(row)
        else:
            cut[row] = column
    result = []
    for number, line in enumerate(lines, 1):
        if number in drop:
            continue
        if number in cut:
            ending = line[len(line.rstrip('\r\n')):]
            result.append(line[:cut[number]].rstrip() + ending)
        else:
            result.append(line)
    return ''.join(result)


def process(path, relative, allowed, dry_run):
    try:
        text, encoding = read_source(path)
    except (OSError, SyntaxError, UnicodeDecodeError) as exc:
        print('%s: READ %s' % (relative, exc))
        return 0, 1
    try:
        spans = comment_spans(text, allowed)
    except (tokenize.TokenError, SyntaxError) as exc:
        print('%s: PARSE %s' % (relative, exc))
        return 0, 1
    if not spans:
        return 0, 0
    updated = strip_spans(text, spans)
    try:
        unchanged = ast.dump(ast.parse(text)) == ast.dump(ast.parse(updated))
    except SyntaxError as exc:
        print('%s: PARSE %s' % (relative, exc))
        return 0, 1
    if not unchanged:
        print('%s: REFUSED (ast tree would change)' % relative)
        return 0, 1
    for row, _column, comment in spans:
        verb = 'would remove' if dry_run else 'removed'
        print('%s:%d: %s %s' % (relative, row, verb, ' '.join(comment.split())[:MAX_TEXT]))
    if not dry_run:
        with open(path, 'w', encoding=encoding, newline='') as handle:
            handle.write(updated)
    return len(spans), 0


def main():
    args = parse_args()
    root = Path(args.root).resolve()
    extensions = {item.strip().lower() if item.strip().startswith('.')
                  else '.' + item.strip().lower()
                  for item in args.ext.split(',') if item.strip()}
    excluded = set(DEFAULT_EXCLUDE)
    excluded.update(item.strip() for item in args.exclude.split(',') if item.strip())
    allowed = [re.compile(item) for item in args.allow]

    total = 0
    affected = 0
    failures = 0
    for path in iter_files(root, extensions, excluded):
        removed, failed = process(path, path.relative_to(root).as_posix(),
                                  allowed, args.dry_run)
        failures += failed
        if removed:
            affected += 1
            total += removed

    print('%s %d comment(s) in %d file(s)' % (
        'would remove' if args.dry_run else 'removed', total, affected))
    if failures:
        print('%d file(s) could not be processed' % failures)
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
