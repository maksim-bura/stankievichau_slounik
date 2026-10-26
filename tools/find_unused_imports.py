"""Report imported names that are never referenced. Run: py -3 tools/find_unused_imports.py [root]"""
import argparse
import ast
import pathlib
import sys

SKIP_PARTS = {'build', 'node_modules', '.git', '__pycache__', 'venv', '.venv'}


def is_type_checking(test):
    if isinstance(test, ast.Name):
        return test.id == 'TYPE_CHECKING'
    if isinstance(test, ast.Attribute):
        return test.attr == 'TYPE_CHECKING'
    return False


def type_checking_names(tree):
    names = set()
    for node in ast.walk(tree):
        if not (isinstance(node, ast.If) and is_type_checking(node.test)):
            continue
        for sub in ast.walk(node):
            if isinstance(sub, ast.Import):
                for alias in sub.names:
                    names.add(alias.asname or alias.name.split('.')[0])
            elif isinstance(sub, ast.ImportFrom):
                for alias in sub.names:
                    names.add(alias.asname or alias.name)
    return names


def all_names(tree):
    names = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(t, ast.Name) and t.id == '__all__'
                   for t in node.targets):
            continue
        try:
            value = ast.literal_eval(node.value)
        except (ValueError, SyntaxError):
            continue
        if isinstance(value, (list, tuple)):
            names.update(item for item in value if isinstance(item, str))
    return names


def imported_names(tree):
    imported = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported[alias.asname or alias.name.split('.')[0]] = node.lineno
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name != '*':
                    imported[alias.asname or alias.name] = node.lineno
    return imported


def referenced_names(tree):
    used = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            used.add(node.id)
        elif isinstance(node, ast.Attribute):
            base = node
            while isinstance(base, ast.Attribute):
                base = base.value
            if isinstance(base, ast.Name):
                used.add(base.id)
    return used


def unused_imports(path):
    try:
        tree = ast.parse(path.read_text(encoding='utf-8'))
    except (SyntaxError, UnicodeDecodeError) as exc:
        return [(0, 'PARSE ' + str(exc))]
    allowed = type_checking_names(tree) | all_names(tree)
    used = referenced_names(tree) | allowed
    imported = imported_names(tree)
    return sorted(
        (line, name) for name, line in imported.items() if name not in used
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('root', nargs='?', default='.')
    args = parser.parse_args()
    root = pathlib.Path(args.root).resolve()
    failures = 0
    for path in sorted(root.rglob('*.py')):
        if path.name == '__init__.py':
            continue
        if SKIP_PARTS & set(path.relative_to(root).parts):
            continue
        for line, name in unused_imports(path):
            print(f'{path.relative_to(root)}:{line}: unused import {name}')
            failures += 1
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
