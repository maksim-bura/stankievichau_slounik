import argparse
import ast
import sys
from pathlib import Path

DEFAULT_EXCLUDE = {
    '.git', '.hg', '.svn', '__pycache__', '.mypy_cache', '.pytest_cache',
    '.venv', 'venv', 'env', 'node_modules', 'build', 'dist', '.idea',
    '.vscode', 'site-packages',
}
RULES = {
    'proxy-style-base': (
        'fatal',
        'a style proxy constructed with a base takes ownership of it; never '
        'pass a live style (self.style(), app.style()); construct with no base '
        'and parent the proxy to the widget',
    ),
    'set-font-family': (
        'fatal',
        'setFontFamily/fontFamily crash this PySide build; use '
        'setFonts/setFontFamilies',
    ),
    'set-document': (
        'advisory',
        'QTextEdit.setDocument does not take ownership; keep a Python '
        'reference and deleteLater() the replaced document',
    ),
}


def parse_args():
    parser = argparse.ArgumentParser(
        description='AST scan for PySide lifetime and font traps.')
    parser.add_argument('--root', default='.')
    parser.add_argument('--ext', default='.py')
    parser.add_argument('--exclude', default='')
    parser.add_argument('--strict', action='store_true',
                        help='treat advisory findings as fatal')
    return parser.parse_args()


def extensions(value):
    return {item.strip().lower() if item.strip().startswith('.')
            else '.' + item.strip().lower()
            for item in value.split(',') if item.strip()}


def iter_files(root, suffixes, excluded):
    for path in sorted(root.rglob('*')):
        if not path.is_file():
            continue
        if path.suffix.lower() not in suffixes:
            continue
        if excluded & set(path.relative_to(root).parts):
            continue
        yield path


def call_name(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def is_style_proxy(name):
    return bool(name) and name[0].isupper() and (
        name == 'QProxyStyle' or name.endswith('Style'))


def scan_tree(tree):
    findings = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = call_name(node.func)
        if is_style_proxy(name) and (node.args or node.keywords):
            findings.append((node.lineno, 'proxy-style-base'))
        elif name in ('setFontFamily', 'fontFamily'):
            findings.append((node.lineno, 'set-font-family'))
        elif name == 'setDocument':
            findings.append((node.lineno, 'set-document'))
    return findings


def scan_file(path):
    findings = []
    try:
        source = path.read_text(encoding='utf-8-sig')
    except (OSError, UnicodeDecodeError) as exc:
        return [(1, 'error', 'cannot read: %s' % exc)]
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        return [(exc.lineno or 1, 'error', 'cannot parse: %s' % exc.msg)]
    for line, rule in scan_tree(tree):
        findings.append((line, rule, RULES[rule][1]))
    return findings


def main():
    args = parse_args()
    root = Path(args.root).resolve()
    if not root.exists():
        print('root not found: %s' % root, file=sys.stderr)
        return 2
    excluded = set(DEFAULT_EXCLUDE)
    if args.exclude:
        excluded |= {item.strip() for item in args.exclude.split(',')
                     if item.strip()}
    findings = []
    scanned = 0
    for path in iter_files(root, extensions(args.ext), excluded):
        scanned += 1
        relative = path.relative_to(root)
        for line, rule, message in scan_file(path):
            severity = RULES[rule][0] if rule in RULES else 'fatal'
            findings.append((severity, relative, line, rule, message))
    findings.sort(key=lambda item: (str(item[1]), item[2], item[3]))
    fatal = 0
    advisory = 0
    for severity, path, line, rule, message in findings:
        print('%s:%s: %s [%s] %s' % (path, line, severity, rule, message))
        if severity == 'fatal':
            fatal += 1
        else:
            advisory += 1
    print('scanned %s files: %s fatal, %s advisory' % (
        scanned, fatal, advisory))
    if fatal or (args.strict and advisory):
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
