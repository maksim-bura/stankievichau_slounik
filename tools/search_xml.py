import argparse
import fnmatch
import re
import sys
from dataclasses import dataclass
from html import unescape
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = TOOLS_DIR.parent
DEFAULT_PATH = PROJECT_ROOT / 'dictionary_app' / 'data'
DEFAULT_GLOB = '*.xml'
DEFAULT_SNIPPET = 160
DEFAULT_LIMIT = 200
DEFAULT_EXCLUDE = {
    '.git', '.hg', '.svn', '__pycache__', '.mypy_cache', '.pytest_cache',
    '.venv', 'venv', 'env', 'node_modules', 'build', 'dist', '.idea',
    '.vscode', 'site-packages',
}
EXIT_MATCH = 0
EXIT_NO_MATCH = 1
EXIT_ERROR = 2
BLOCK_TAGS = {'d', 'entry'}
TAG_PATTERN = (
    r'<(?P<close>/)?(?P<name>[A-Za-z_][\w:.-]*)'
    r'(?P<body>(?:"[^"]*"|\'[^\']*\'|[^>"\'])*)>'
)
TOKEN_RE = re.compile(
    r'<!--.*?-->|<!\[CDATA\[.*?\]\]>|' + TAG_PATTERN,
    re.DOTALL,
)
TAG_MARKUP_RE = re.compile(r'<[^>]+>')
WHITESPACE_RE = re.compile(r'\s+')
HEADWORD_RE = re.compile(r'<hw\b[^>]*>.*?</hw>', re.DOTALL)


@dataclass
class Block:
    tag: str
    start: int
    end: int


def build_parser():
    parser = argparse.ArgumentParser(
        description=(
            'Search marked-up XML files recursively and show the headword(s) '
            'of each match.'
        )
    )
    parser.add_argument(
        'query', nargs='?', help='literal text or regular expression',
    )
    parser.add_argument(
        'paths', nargs='*',
        help='files or directories (default: dictionary_app/data)',
    )
    parser.add_argument(
        '--glob', default=DEFAULT_GLOB,
        help='comma-separated file patterns (default: *.xml)',
    )
    parser.add_argument(
        '--exclude', default='',
        help='comma-separated path parts to skip',
    )
    parser.add_argument(
        '--ignore-case', action='store_true',
        help='match case-insensitively',
    )
    parser.add_argument(
        '--regex', action='store_true',
        help='treat the query as a regular expression',
    )
    parser.add_argument(
        '--context', type=int, default=0,
        help='lines of context around each match (default: 0)',
    )
    parser.add_argument(
        '--snippet', type=int, default=DEFAULT_SNIPPET,
        help='printed characters per line, 0 = full line (default: 160)',
    )
    parser.add_argument(
        '--limit', type=int, default=DEFAULT_LIMIT,
        help='matching lines to print per file, 0 = all (default: 200)',
    )
    parser.add_argument(
        '--count', action='store_true',
        help='print per-file match counts and a total',
    )
    parser.add_argument(
        '--files-with-matches', action='store_true',
        help='print only paths that contain a match',
    )
    return parser


def parse_args(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.query is None:
        parser.print_help()
        parser.exit(EXIT_ERROR)
    return args


def pattern_matches(name, relative, pattern):
    if '/' in pattern or '\\' in pattern:
        return fnmatch.fnmatch(relative, pattern.replace('\\', '/'))
    return fnmatch.fnmatch(name, pattern)


def iter_files(paths, patterns, excluded):
    seen = set()
    for raw in paths:
        path = Path(raw)
        if path.is_file():
            key = path.resolve()
            if key not in seen:
                seen.add(key)
                yield path
            continue
        if not path.is_dir():
            print('%s: not found' % raw, file=sys.stderr)
            continue
        for candidate in sorted(path.rglob('*')):
            if not candidate.is_file():
                continue
            relative = candidate.relative_to(path)
            if excluded & set(relative.parts):
                continue
            relative_text = relative.as_posix()
            if not any(pattern_matches(candidate.name, relative_text, item)
                       for item in patterns):
                continue
            key = candidate.resolve()
            if key in seen:
                continue
            seen.add(key)
            yield candidate


def display_path(path):
    try:
        return path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def read_text(path):
    return path.read_text(encoding='utf-8-sig')


def line_starts(text):
    starts = []
    position = 0
    for line in text.splitlines(keepends=True):
        starts.append(position)
        position += len(line)
    return starts


def scan_blocks(text):
    blocks = []
    stack = []
    for match in TOKEN_RE.finditer(text):
        name = match.group('name')
        if name is None:
            continue
        body = match.group('body') or ''
        if match.group('close'):
            for depth in range(len(stack) - 1, -1, -1):
                if stack[depth].tag == name:
                    stack[depth].end = match.end()
                    del stack[depth:]
                    break
            continue
        if body.rstrip().endswith('/') or name not in BLOCK_TAGS:
            continue
        block = Block(
            name, match.start(), match.end(),
        )
        blocks.append(block)
        stack.append(block)
    headwords = []
    for match in HEADWORD_RE.finditer(text):
        parent = enclosing_block(match.start(), blocks, 'd')
        if parent is None:
            parent = enclosing_block(match.start(), blocks, 'entry')
        headwords.append((match.start(), match.end(), parent))
    return blocks, headwords


def headword_text(fragment):
    text = TAG_MARKUP_RE.sub('', fragment)
    return WHITESPACE_RE.sub(' ', unescape(text)).strip()


def enclosing_block(offset, blocks, tag):
    candidates = [
        block for block in blocks
        if block.tag == tag and block.start <= offset < block.end
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda block: block.end - block.start)


def headwords_at(text, offset, blocks, headwords):
    block = enclosing_block(offset, blocks, 'd')
    if block is None:
        block = enclosing_block(offset, blocks, 'entry')
    if block is None:
        return []
    result = []
    for start, end, parent in headwords:
        if parent is not block:
            continue
        headword = headword_text(text[start:end])
        if headword and headword not in result:
            result.append(headword)
    return result


def collect_line_headwords(text, starts, found, blocks, headwords):
    result = {}
    for index, matches in found.items():
        if index >= len(starts):
            continue
        line_result = []
        for start, _end in matches:
            for headword in headwords_at(
                text, starts[index] + start, blocks, headwords,
            ):
                if headword not in line_result:
                    line_result.append(headword)
        if line_result:
            result[index] = line_result
    return result


def clip(line, position, width):
    if width <= 0 or len(line) <= width:
        return line
    start = max(0, position - width // 3)
    end = min(len(line), start + width)
    start = max(0, end - width)
    prefix = '...' if start else ''
    suffix = '...' if end < len(line) else ''
    return prefix + line[start:end] + suffix


def matches_for_line(line, pattern):
    return [(match.start(), match.end()) for match in pattern.finditer(line)]


def collect_matches(lines, pattern):
    found = {}
    for index, line in enumerate(lines):
        matches = matches_for_line(line, pattern)
        if matches:
            found[index] = matches
    return found


def print_context(
    display, lines, found, context, snippet, limit, line_headwords,
):
    printed_until = -1
    shown = 0
    for index in sorted(found):
        if limit and shown >= limit:
            break
        start = max(0, index - context)
        end = min(len(lines), index + context + 1)
        if printed_until >= 0 and start > printed_until + 1:
            print('--')
        for current in range(max(start, printed_until + 1), end):
            if current in found:
                column = found[current][0][0] + 1
                headwords = line_headwords.get(current)
                if headwords:
                    print('%s:%d:%d  headword(s): %s' % (
                        display, current + 1, column,
                        ', '.join(headwords),
                    ))
                    print('    %s' % clip(
                        lines[current], column - 1, snippet,
                    ))
                else:
                    print('%s:%d:%d: %s' % (
                        display, current + 1, column,
                        clip(lines[current], column - 1, snippet),
                    ))
                shown += 1
                if limit and shown >= limit:
                    return shown
            else:
                print('%s-%d- %s' % (
                    display, current + 1,
                    clip(lines[current], 0, snippet),
                ))
        printed_until = max(printed_until, end - 1)
    return shown


def main(argv=None):
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    args = parse_args(argv)

    if not args.query:
        print('query must not be empty', file=sys.stderr)
        return EXIT_ERROR
    try:
        flags = re.IGNORECASE if args.ignore_case else 0
        pattern = re.compile(
            args.query if args.regex else re.escape(args.query), flags,
        )
    except re.error as exc:
        print('invalid regular expression: %s' % exc, file=sys.stderr)
        return EXIT_ERROR

    patterns = [item.strip() for item in args.glob.split(',') if item.strip()]
    excluded = set(DEFAULT_EXCLUDE)
    excluded.update(item.strip() for item in args.exclude.split(',')
                    if item.strip())
    paths = args.paths or [str(DEFAULT_PATH)]
    files = list(iter_files(paths, patterns, excluded))
    if not files:
        print('no files matched "%s" under %s' % (
            args.glob, ', '.join(paths)), file=sys.stderr)
        return EXIT_ERROR

    total_matches = 0
    total_lines = 0
    shown_lines = 0
    files_with_matches = 0
    had_error = False
    for path in files:
        display = display_path(path)
        try:
            text = read_text(path)
        except (OSError, UnicodeDecodeError) as exc:
            print('%s: READ %s' % (display, exc), file=sys.stderr)
            had_error = True
            continue
        lines = text.splitlines()
        found = collect_matches(lines, pattern)
        file_matches = sum(len(matches) for matches in found.values())
        if file_matches:
            files_with_matches += 1
            total_matches += file_matches
            total_lines += len(found)
        if args.count:
            print('%s:%d' % (display, file_matches))
            continue
        if args.files_with_matches:
            if file_matches:
                print(display)
            continue
        if found:
            blocks, headwords = scan_blocks(text)
            line_headwords = collect_line_headwords(
                text, line_starts(text), found, blocks, headwords,
            )
            shown_lines += print_context(
                display, lines, found, max(0, args.context),
                max(0, args.snippet), max(0, args.limit),
                line_headwords,
            )

    if args.count:
        print('total:%d' % total_matches)
    elif args.files_with_matches:
        pass
    else:
        print('%d match(es) in %d file(s)' % (
            total_matches, files_with_matches,
        ))
        if args.limit and shown_lines < total_lines:
            print('%d matching line(s) not shown (--limit %d)' % (
                total_lines - shown_lines, args.limit))

    if had_error:
        return EXIT_ERROR
    return EXIT_MATCH if total_matches else EXIT_NO_MATCH


if __name__ == '__main__':
    sys.exit(main())
