"""Apply module renames, file moves, and symbol splits, rewriting only import statements.

Run: py -3 tools/rewrite_imports.py plan.json            (dry run)
     py -3 tools/rewrite_imports.py plan.json --apply

plan.json:
{
  "files":   {"old/path.py": "new/path.py"},
  "modules": {"old.module": "new.module"},
  "splits":  {"old.module": {"Symbol": "new.module"}}
}

Import blocks are re-wrapped at 96 columns. Every touched file is re-parsed with
ast after rewriting; the script stops before writing if any file would not parse.
"""
import argparse
import ast
import io
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

LINE_MAX = 96
FROM_PAREN = re.compile(
    r'^(?P<indent>[ \t]*)from[ \t]+(?P<module>[.\w]*)[ \t]+import[ \t]*\((?P<body>[^)]*)\)[ \t]*$',
    re.DOTALL | re.MULTILINE)
FROM_PLAIN = re.compile(
    r'^(?P<indent>[ \t]*)from[ \t]+(?P<module>[.\w]*)[ \t]+import[ \t]+(?P<body>[^(\n]+)$',
    re.MULTILINE)
IMPORT_PLAIN = re.compile(
    r'^(?P<indent>[ \t]*)import[ \t]+(?P<module>[\w.]+)(?:[ \t]+as[ \t]+(?P<alias>\w+))?[ \t]*$',
    re.MULTILINE)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('plan')
    parser.add_argument('--root', default='.')
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--no-move', action='store_true')
    return parser.parse_args()


def module_name(path, root):
    relative = Path(path).resolve().relative_to(root)
    parts = list(relative.with_suffix('').parts)
    if parts and parts[-1] == '__init__':
        parts.pop()
    return '.'.join(parts)


def package_of(module):
    return module.rsplit('.', 1)[0] if '.' in module else ''


def resolve_relative(module, level, file_module):
    if not level:
        return module
    package = package_of(file_module)
    for _ in range(level - 1):
        package = package_of(package)
    return (package + '.' + module).strip('.') if module else package


def relative_to_package(module, package):
    if module == package:
        return '.'
    prefix = package + '.'
    if module.startswith(prefix):
        return '.' + module[len(prefix):]
    return None


def split_symbols(body):
    body = body.replace('\n', ' ')
    symbols = []
    for part in body.split(','):
        part = part.strip()
        if not part:
            continue
        symbols.append(part)
    return symbols


def wrap_import(indent, module, symbols):
    if not symbols:
        return ['%sfrom %s import ()' % (indent, module)]
    single = '%sfrom %s import %s' % (indent, module, ', '.join(symbols))
    if len(single) <= LINE_MAX:
        return [single]
    lines = ['%sfrom %s import (' % (indent, module)]
    current = indent + '    '
    for index, symbol in enumerate(symbols):
        piece = symbol + (',' if index < len(symbols) - 1 else '')
        candidate = current + (' ' if current.strip() else '') + piece
        if current.strip() and len(candidate) > LINE_MAX:
            lines.append(current.rstrip())
            current = indent + '    ' + piece
        else:
            current = candidate
    lines.append(current.rstrip())
    lines.append(indent + ')')
    return lines


def render_from(indent, module, symbols, was_relative, file_module):
    if was_relative:
        relative = relative_to_package(module, package_of(file_module))
        if relative is not None:
            if relative == '.':
                return wrap_import(indent, '.', symbols)
            return wrap_import(indent, relative, symbols)
    return wrap_import(indent, module, symbols)


def rewrite_text(text, file_module, module_map, splits):
    def replace_from(match):
        indent = match.group('indent')
        module = match.group('module')
        body = match.group('body')
        level = len(module) - len(module.lstrip('.'))
        base = resolve_relative(module.lstrip('.'), level, file_module)
        was_relative = level > 0
        if base == '__future__' or base.startswith('__future__'):
            return match.group(0)
        target = module_map.get(base, base)
        groups = {}
        order = []
        for symbol in split_symbols(body):
            name = symbol.split()[0]
            destination = splits.get(base, {}).get(name, target)
            if destination not in groups:
                groups[destination] = []
                order.append(destination)
            groups[destination].append(symbol)
        rendered = []
        for destination in order:
            rendered.extend(render_from(indent, destination, groups[destination],
                                        was_relative, file_module))
        return '\n'.join(rendered)

    def replace_import(match):
        indent = match.group('indent')
        module = match.group('module')
        target = module_map.get(module, module)
        alias = match.group('alias')
        suffix = ' as ' + alias if alias else ''
        return '%simport %s%s' % (indent, target, suffix)

    text = FROM_PAREN.sub(replace_from, text)
    text = FROM_PLAIN.sub(replace_from, text)
    text = IMPORT_PLAIN.sub(replace_import, text)
    return text


def move_file(root, old, new):
    old_path = root / old
    new_path = root / new
    new_path.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(['git', 'mv', old, new], cwd=str(root),
                            capture_output=True, text=True)
    if result.returncode != 0:
        shutil.move(str(old_path), str(new_path))


def main():
    args = parse_args()
    root = Path(args.root).resolve()
    plan = json.loads(Path(args.plan).read_text(encoding='utf-8'))
    files = plan.get('files', {})
    modules = dict(plan.get('modules', {}))
    splits = plan.get('splits', {})

    if args.apply and not args.no_move:
        for old, new in files.items():
            if (root / old).exists():
                move_file(root, old, new)
                print('moved %s -> %s' % (old, new))
    for old, new in files.items():
        modules[module_name(root / old, root)] = module_name(root / new, root)
    for old, new in list(modules.items()):
        if old == new:
            del modules[old]

    changed = 0
    planned = 0
    failures = []
    for path in sorted(root.rglob('*.py')):
        relative = path.relative_to(root)
        if any(part in {'.git', '__pycache__', '.venv', 'venv', 'build',
                        'dist', 'node_modules'} for part in relative.parts):
            continue
        file_module = module_name(path, root)
        text = io.open(path, encoding='utf-8', newline='').read()
        updated = rewrite_text(text, file_module, modules, splits)
        if updated == text:
            continue
        planned += 1
        try:
            ast.parse(updated)
        except SyntaxError as exc:
            failures.append('%s: %s' % (relative.as_posix(), exc))
            continue
        if args.apply:
            io.open(path, 'w', encoding='utf-8', newline='').write(updated)
            changed += 1
        else:
            print('would rewrite %s' % relative.as_posix())

    print('modules mapped: %d, files with import changes: %d, written: %d' % (
        len(modules), planned, changed))
    if failures:
        print('REFUSED (syntax errors):')
        for failure in failures:
            print('  - %s' % failure)
        return 1
    if not args.apply and planned:
        print('dry run only; re-run with --apply')
    if args.apply:
        result = subprocess.run(
            [sys.executable, '-m', 'compileall', '-q', str(root)],
            capture_output=True, text=True)
        if result.returncode != 0:
            print('compileall failed:\n%s' % (result.stdout + result.stderr))
            return 1
        print('compileall: ok; next run tools/check_cleanup.py')
    return 0


if __name__ == '__main__':
    sys.exit(main())
