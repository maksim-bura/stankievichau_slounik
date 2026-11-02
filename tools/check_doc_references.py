"""Check documentation cross-references: numbered sections and repo paths.

Run: py -3 tools/check_doc_references.py
     py -3 tools/check_doc_references.py --sections-from docs/index.md
     py -3 tools/check_doc_references.py --checks sections --ignore-glob 'out/*'

Every `§N` / `§N.M` must match a numbered heading in the same document, or in a
document passed with --sections-from. Every backticked repo path must exist
(relative to the root or to the file that mentions it); a token counts as a path
when its first segment exists at the root or its extension is in --path-ext.
Paths covered by .gitignore are skipped, so generated outputs never fail the
check. Exits 1 when a reference does not resolve, 0 when the docs are consistent.
"""
import argparse
import re
import sys
from fnmatch import fnmatch
from pathlib import Path

DEFAULT_EXCLUDE = {
    '.git', '.hg', '.svn', '__pycache__', '.mypy_cache', '.pytest_cache',
    '.venv', 'venv', 'env', 'node_modules', 'build', 'dist', '.idea',
    '.vscode', 'site-packages',
}
HEADING = re.compile(r'^#{1,6}\s+(\d+(?:\.\d+)*)(?=[.)\s]|$)')
SECTION_REF = re.compile(r'\u00a7(\d+(?:\.\d+)*)')
INLINE_CODE = re.compile(r'`([^`\n]+)`')
PATH_TOKEN = re.compile(r'^[\w./\\-]+$')
PLACEHOLDER_CHARS = set('*?<>{}|$%')
TRAILING_PUNCTUATION = '.,;:)]}>'
CHECKS = ('sections', 'paths')
DEFAULT_PATH_EXT = '.py,.md,.json,.xml,.txt,.toml,.cfg,.ini,.yaml,.yml,.db,.csv'


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', default='.')
    parser.add_argument('--ext', default='.md')
    parser.add_argument('--exclude', default='')
    parser.add_argument('--sections-from', action='append', default=[])
    parser.add_argument('--ignore-glob', action='append', default=[])
    parser.add_argument('--checks', default='sections,paths')
    parser.add_argument('--path-ext', default=DEFAULT_PATH_EXT)
    parser.add_argument('--show-ignored', action='store_true')
    parser.add_argument('--no-gitignore', action='store_true')
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


def sections_of(text):
    found = set()
    for line in text.splitlines():
        match = HEADING.match(line)
        if match:
            found.add(match.group(1))
    return found


def resolves(number, declared):
    if number in declared:
        return True
    return any(section.startswith(number + '.') for section in declared)


def gitignore_patterns(root):
    patterns = []
    path = root / '.gitignore'
    try:
        text = path.read_text(encoding='utf-8')
    except OSError:
        return patterns
    for line in text.splitlines():
        entry = line.strip().replace('\\', '/')
        if not entry or entry.startswith('#') or entry.startswith('!'):
            continue
        entry = entry.rstrip('/')
        if entry.startswith('./'):
            entry = entry[2:]
        elif entry.startswith('/'):
            entry = entry[1:]
        if entry:
            patterns.append(entry)
    return patterns


def is_ignored(path, patterns):
    normalised = path.replace('\\', '/').rstrip('/')
    parts = normalised.split('/')
    for pattern in patterns:
        if pattern.endswith('/*') and fnmatch(normalised, pattern[:-2]):
            return True
        if fnmatch(normalised, pattern) or fnmatch(normalised, pattern + '/*'):
            return True
        if pattern.startswith('**/'):
            tail = pattern[3:]
            if fnmatch(normalised, tail) or fnmatch(normalised, '*/' + tail):
                return True
        if '/' in pattern:
            if normalised.startswith(pattern + '/'):
                return True
        elif any(fnmatch(part, pattern) for part in parts):
            return True
    return False


def path_candidate(token, root, path_extensions):
    if not token or ' ' in token or '\t' in token:
        return None
    if '://' in token or token.lower().startswith('www.'):
        return None
    if any(char in PLACEHOLDER_CHARS for char in token):
        return None
    cleaned = token.rstrip(TRAILING_PUNCTUATION)
    if '/' not in cleaned or not PATH_TOKEN.match(cleaned):
        return None
    head = cleaned.lstrip('/\\').split('/')[0]
    if root.joinpath(head).exists():
        return cleaned
    if Path(cleaned).suffix.lower() in path_extensions:
        return cleaned
    return None


def check_sections(relative, text, declared, extra, report):
    count = 0
    unresolved = 0
    for number, line in enumerate(text.splitlines(), 1):
        for match in SECTION_REF.finditer(line):
            count += 1
            target = match.group(1)
            if not resolves(target, declared) and not resolves(target, extra):
                unresolved += 1
                report.append('%s:%d: missing section \u00a7%s' % (relative, number, target))
    return count, unresolved


def check_paths(root, path, relative, text, patterns, path_extensions, report, ignored):
    count = 0
    unresolved = 0
    for number, line in enumerate(text.splitlines(), 1):
        for match in INLINE_CODE.finditer(line):
            token = path_candidate(match.group(1).strip(), root, path_extensions)
            if token is None:
                continue
            count += 1
            cleaned = token.lstrip('/\\')
            if (root / cleaned).exists() or (path.parent / cleaned).exists():
                continue
            if is_ignored(cleaned, patterns):
                ignored.append('%s:%d: %s' % (relative, number, token))
                continue
            unresolved += 1
            report.append('%s:%d: missing path `%s`' % (relative, number, token))
    return count, unresolved


def main():
    args = parse_args()
    root = Path(args.root).resolve()
    suffixes = extensions(args.ext)
    excluded = set(DEFAULT_EXCLUDE)
    excluded.update(item.strip() for item in args.exclude.split(',') if item.strip())
    checks = {item.strip() for item in args.checks.split(',') if item.strip()}
    unknown = checks - set(CHECKS)
    if unknown:
        print('unknown check(s): %s (expected %s)' % (', '.join(sorted(unknown)),
                                                      ', '.join(CHECKS)))
        return 1

    patterns = []
    if not args.no_gitignore:
        patterns.extend(gitignore_patterns(root))
    patterns.extend(item.strip() for item in args.ignore_glob if item.strip())
    path_extensions = {item.strip().lower() if item.strip().startswith('.')
                       else '.' + item.strip().lower()
                       for item in args.path_ext.split(',') if item.strip()}

    paths = list(iter_files(root, suffixes, excluded))
    declared = {}
    texts = {}
    for path in paths:
        try:
            texts[path] = path.read_text(encoding='utf-8')
        except UnicodeDecodeError as exc:
            print('%s: ENCODING %s' % (path.relative_to(root).as_posix(), exc))
            return 1
        declared[path] = sections_of(texts[path])

    extra = set()
    for item in args.sections_from:
        source = Path(item)
        if not source.is_absolute():
            source = root / item
        try:
            extra.update(sections_of(source.read_text(encoding='utf-8')))
        except (OSError, UnicodeDecodeError) as exc:
            print('%s: SECTIONS-FROM %s' % (item, exc))
            return 1

    report = []
    ignored = []
    section_refs = section_missing = 0
    path_refs = path_missing = 0
    for path in paths:
        relative = path.relative_to(root).as_posix()
        text = texts[path]
        if 'sections' in checks:
            count, unresolved = check_sections(relative, text, declared[path],
                                               extra, report)
            section_refs += count
            section_missing += unresolved
        if 'paths' in checks:
            count, unresolved = check_paths(root, path, relative, text, patterns,
                                            path_extensions, report, ignored)
            path_refs += count
            path_missing += unresolved

    for line in report:
        print(line)
    if args.show_ignored:
        for line in ignored:
            print('ignored %s' % line)
    if 'sections' in checks:
        print('sections: %d reference(s), %d unresolved' % (section_refs,
                                                            section_missing))
    if 'paths' in checks:
        print('paths: %d reference(s), %d unresolved, %d ignored' % (
            path_refs, path_missing, len(ignored)))
    return 1 if (section_missing or path_missing) else 0


if __name__ == '__main__':
    sys.exit(main())
