"""Query data files without loading them into the conversation.

Run: py -3 tools/inspect_data.py --count
     py -3 tools/inspect_data.py --lookup "word" --limit 10
     py -3 tools/inspect_data.py --duplicates entry/id
     py -3 tools/inspect_data.py --attribute-audit

Read-only: no query opens a file for writing, creates a file, or touches the
database. The tag scan is line-oriented and tolerant of malformed markup, so a
broken file still reports path:line instead of aborting the run. Records are
discovered at runtime (the most common child of the root element) unless
--tag / --record names one. Exit 0 when the query ran, 1 when no file matched
or a file could not be read.
"""
import argparse
import bisect
import fnmatch
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

DEFAULT_EXCLUDE = {
    '.git', '.hg', '.svn', '__pycache__', '.mypy_cache', '.pytest_cache',
    '.venv', 'venv', 'env', 'node_modules', 'build', 'dist', '.idea',
    '.vscode', 'site-packages',
}
DEFAULT_GLOB = '*.xml,*.txt'
TAG = re.compile(r'<\s*(/?)\s*([A-Za-z_][\w.:-]*)'
                 r'((?:"[^"]*"|\'[^\']*\'|[^>"\'])*)>')
ATTR = re.compile(r'([A-Za-z_][\w.:-]*)\s*=\s*(?:"([^"]*)"|\'([^\']*)\')')
MAX_TEXT = 120
MAX_VALUE = 40
MAX_MEMBERS = 5
MAX_RARE = 20


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', default='.')
    parser.add_argument('--glob', default=DEFAULT_GLOB)
    parser.add_argument('--exclude', default='')
    parser.add_argument('--tag', default='')
    parser.add_argument('--record', default='')
    parser.add_argument('--limit', type=int, default=20)
    parser.add_argument('--top', type=int, default=3)
    parser.add_argument('--context', type=int, default=0)
    parser.add_argument('--snippet', type=int, default=MAX_TEXT)
    parser.add_argument('--ignore-case', action='store_true')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--count', action='store_true')
    group.add_argument('--lookup', default=None)
    group.add_argument('--duplicates', default=None)
    group.add_argument('--attribute-audit', action='store_true')
    return parser.parse_args()


def limit_of(value):
    return None if value <= 0 else value


def iter_files(root, patterns, excluded):
    for path in sorted(root.rglob('*')):
        if not path.is_file():
            continue
        if excluded & set(path.relative_to(root).parts):
            continue
        relative = path.relative_to(root).as_posix()
        if any(pattern_matches(path.name, relative, item)
               for item in patterns):
            yield path, relative


def pattern_matches(name, relative, pattern):
    if '/' in pattern or '\\' in pattern:
        return fnmatch.fnmatch(relative, pattern.replace('\\', '/'))
    return fnmatch.fnmatch(name, pattern)


def read_text(path):
    return path.read_text(encoding='utf-8-sig')


def line_starts(text):
    starts = [0]
    index = text.find('\n')
    while index != -1:
        starts.append(index + 1)
        index = text.find('\n', index + 1)
    return starts


def scan_tags(text):
    starts = line_starts(text)
    for match in TAG.finditer(text):
        body = match.group(3) or ''
        yield (bisect.bisect_right(starts, match.start()),
               match.group(2), bool(match.group(1)),
               body.rstrip().endswith('/'), body)


def parse_attributes(body):
    found = {}
    for match in ATTR.finditer(body):
        value = match.group(2) if match.group(2) is not None else match.group(3)
        found[match.group(1)] = value
    return found


def scan_elements(text):
    stack = []
    elements = []
    for line, name, closing, self_closing, body in scan_tags(text):
        if closing:
            for depth in range(len(stack) - 1, -1, -1):
                if stack[depth] == name:
                    del stack[depth:]
                    break
            continue
        parent = stack[-1] if stack else None
        elements.append((name, parent, line, parse_attributes(body)))
        if not self_closing:
            stack.append(name)
    return elements


def discover_record(elements, requested):
    if requested:
        return requested
    if not elements:
        return None
    root = elements[0][0]
    children = Counter(name for name, parent, _line, _attrs in elements
                       if parent == root)
    if children:
        return children.most_common(1)[0][0]
    tags = Counter(name for name, _parent, _line, _attrs in elements)
    return tags.most_common(1)[0][0]


def clip(line, needle, width, ignore_case):
    text = line.strip()
    if len(text) <= width:
        return text
    hay = text.lower() if ignore_case else text
    position = hay.find(needle)
    if position < 0:
        return text[:width] + '...'
    start = max(0, position - width // 3)
    end = min(len(text), start + width)
    start = max(0, end - width)
    prefix = '...' if start else ''
    suffix = '...' if end < len(text) else ''
    return prefix + text[start:end] + suffix


def short(value, width=MAX_VALUE):
    text = ' '.join(value.split())
    return text if len(text) <= width else text[:width] + '...'


def report_count(files, args):
    rows = []
    total_records = 0
    failures = 0
    for path, relative in files:
        try:
            text = read_text(path)
        except (OSError, UnicodeDecodeError) as exc:
            print('%s: READ %s' % (relative, exc))
            failures += 1
            continue
        elements = scan_elements(text)
        record = discover_record(elements, args.record or args.tag)
        tags = Counter(name for name, _parent, _line, _attrs in elements)
        records = tags[record] if record else 0
        total_records += records
        top = ', '.join('%s=%d' % item for item in tags.most_common(6))
        rows.append((relative, path.stat().st_size, len(text.splitlines()),
                     len(elements), record or '-', records, top))
    name_width = max([len(row[0]) for row in rows] + [len('file')])
    print('%-*s %9s %8s %7s %-12s %8s  %s' % (
        name_width, 'file', 'bytes', 'lines', 'tags', 'record', 'records',
        'top tags'))
    for relative, size, lines, tags, record, records, top in rows:
        print('%-*s %9d %8d %7d %-12s %8d  %s' % (
            name_width, relative, size, lines, tags, record, records, top))
    print('count: %d file(s), %d record(s) total' % (len(rows), total_records))
    return 1 if failures else 0


def report_lookup(files, args):
    needle = args.lookup
    hay = needle.lower() if args.ignore_case else needle
    limit = limit_of(args.limit)
    total = 0
    shown = 0
    failures = 0
    for path, relative in files:
        try:
            text = read_text(path)
        except (OSError, UnicodeDecodeError) as exc:
            print('%s: READ %s' % (relative, exc))
            failures += 1
            continue
        lines = text.splitlines()
        printed = set()
        for index, line in enumerate(lines):
            target = line.lower() if args.ignore_case else line
            hits = target.count(hay)
            if not hits:
                continue
            total += hits
            if limit is not None and shown >= limit:
                continue
            shown += 1
            first = max(0, index - args.context)
            last = min(len(lines), index + args.context + 1)
            for offset in range(first, last):
                if offset in printed:
                    continue
                printed.add(offset)
                marker = '>' if offset == index else ' '
                print('%s %s:%d: %s' % (
                    marker, relative, offset + 1,
                    clip(lines[offset], hay, args.snippet, args.ignore_case)))
    print('lookup "%s": %d match(es), %d line(s) shown%s' % (
        needle, total, shown, '' if limit is None or total <= shown
        else ', limit %d' % limit))
    return 1 if failures else 0


def duplicate_spec(args):
    spec = args.duplicates
    if '/' in spec:
        tag, attribute = spec.split('/', 1)
        return tag or args.tag, attribute
    return args.tag, spec


def report_duplicates(files, args):
    tag_filter, attribute = duplicate_spec(args)
    groups = defaultdict(list)
    failures = 0
    for path, relative in files:
        try:
            text = read_text(path)
        except (OSError, UnicodeDecodeError) as exc:
            print('%s: READ %s' % (relative, exc))
            failures += 1
            continue
        for name, _parent, line, attributes in scan_elements(text):
            if tag_filter and name != tag_filter:
                continue
            if attribute not in attributes:
                continue
            groups[attributes[attribute]].append((relative, line, name))
    duplicate_groups = sorted((value, members) for value, members in groups.items()
                              if len(members) > 1)
    label = '%s/@%s' % (tag_filter, attribute) if tag_filter else '@' + attribute
    limit = limit_of(args.limit)
    print('duplicates: %s' % label)
    shown = 0
    for value, members in duplicate_groups:
        if limit is not None and shown >= limit:
            break
        shown += 1
        places = []
        for relative, line, name in members[:MAX_MEMBERS]:
            places.append('%s:%d%s' % (
                relative, line, '' if tag_filter else ' [%s]' % name))
        if len(members) > MAX_MEMBERS:
            places.append('+%d more' % (len(members) - MAX_MEMBERS))
        print('  %s: %s' % (short(value, 60), ', '.join(places)))
    print('duplicates: %d group(s), %d element(s)%s' % (
        len(duplicate_groups),
        sum(len(members) for _value, members in duplicate_groups),
        '' if limit is None or len(duplicate_groups) <= shown
        else ', %d shown' % shown))
    return 1 if failures else 0


def report_attribute_audit(files, args):
    tags = Counter()
    pairs = defaultdict(Counter)
    failures = 0
    for path, relative in files:
        try:
            text = read_text(path)
        except (OSError, UnicodeDecodeError) as exc:
            print('%s: READ %s' % (relative, exc))
            failures += 1
            continue
        for name, _parent, _line, attributes in scan_elements(text):
            if args.tag and name != args.tag:
                continue
            tags[name] += 1
            for attribute, value in attributes.items():
                pairs[(name, attribute)][value] += 1
    if not pairs:
        print('attribute audit: no attributes found')
        return 1 if failures else 0
    tag_width = max([len(name) for name, _attribute in pairs] + [len('tag')])
    attr_width = max([len(attribute) for _name, attribute in pairs]
                     + [len('attr')])
    print('%-*s %-*s %7s %9s  %s' % (
        tag_width, 'tag', attr_width, 'attr', 'count', 'distinct', 'sample'))
    for (name, attribute), values in sorted(
            pairs.items(), key=lambda item: (item[0][0], -sum(item[1].values()))):
        sample = ', '.join(short(value) for value, _count
                           in values.most_common(args.top))
        print('%-*s %-*s %7d %9d  %s' % (
            tag_width, name, attr_width, attribute, sum(values.values()),
            len(values), sample))
    rare = ['%s/@%s' % pair for pair, values in pairs.items()
            if sum(values.values()) == 1]
    print('attribute audit: %d tag(s), %d attribute pair(s), %d element(s)'
          % (len(tags), len(pairs), sum(tags.values())))
    if rare:
        print('used once: %s%s' % (
            ', '.join(sorted(rare)[:MAX_RARE]),
            '' if len(rare) <= MAX_RARE else ', +%d more' % (len(rare) - MAX_RARE)))
    return 1 if failures else 0


def main():
    args = parse_args()
    root = Path(args.root).resolve()
    patterns = [item.strip() for item in args.glob.split(',') if item.strip()]
    excluded = set(DEFAULT_EXCLUDE)
    excluded.update(item.strip() for item in args.exclude.split(',')
                    if item.strip())
    files = list(iter_files(root, patterns, excluded))
    if not files:
        print('no files matched "%s" under %s' % (args.glob, root))
        return 1
    if args.count:
        return report_count(files, args)
    if args.lookup is not None:
        return report_lookup(files, args)
    if args.duplicates is not None:
        return report_duplicates(files, args)
    return report_attribute_audit(files, args)


if __name__ == '__main__':
    sys.exit(main())
