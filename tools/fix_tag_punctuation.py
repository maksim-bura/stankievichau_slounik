"""Review punctuation that follows a closing tag.

Run: py -3 tools/fix_tag_punctuation.py
     py -3 tools/fix_tag_punctuation.py --apply
     py -3 tools/fix_tag_punctuation.py dictionary_app/data/dictionary/dictionary_D.xml

A candidate is an opening tag, its content, its closing tag, and the run of
Unicode punctuation that immediately follows the closing tag. The prepared
`after` text moves that run inside the closing tag. Some runs are skipped
because moving them would change the rendered form (`</hw>.`, `</t>.`, any
`</g>—`, `</see>`, `</n>`, a `<src>` containing `<b>`, and similar). Adjacent
`<src>` runs separated by `;` or `,` are merged into one source span, even when
the separator follows other punctuation or the last source has no trailing
punctuation. A trailing em dash is left outside `<g>`/`<src>`; only the
punctuation before it is absorbed. Each candidate is presented one at a time:
Enter skips it, `y` writes the prepared text, and any other input replaces the
whole candidate span. Accepted changes are written immediately and the file's
existing line endings are preserved.
"""
import argparse
import re
import sys
import unicodedata
from dataclasses import dataclass
from html import unescape
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = TOOLS_DIR.parent
DEFAULT_PATH = PROJECT_ROOT / 'dictionary_app' / 'data'

TAG_PATTERN = (
    r'<(?P<close>/)?(?P<name>[A-Za-z_][\w:.-]*)'
    r'(?P<body>(?:"[^"]*"|\'[^\']*\'|[^>"\'])*)>'
)
TOKEN_RE = re.compile(
    r'<!--.*?-->|<!\[CDATA\[.*?\]\]>|' + TAG_PATTERN,
    re.DOTALL,
)
PUNCTUATION_CATEGORY_PREFIX = 'P'
IDENTITY_TAGS = {'hw', 'see'}
SKIP_TAGS = {'see', 'n'}
FRAGMENT_MAX = 200
YES_ANSWER = 'y'
SOURCE_SEPARATORS = {';', ','}
DASH_SPLIT_TAGS = {'g', 'src'}
SRC_ELEMENT_RE = re.compile(r'<src(?:\s[^>]*)?>.*?</src>', re.DOTALL)
HEADWORD_RE = re.compile(r'<hw\b[^>]*>(.*?)</hw>', re.DOTALL)
BOLD_TAG_RE = re.compile(r'<b\b')
TAG_MARKUP_RE = re.compile(r'<[^>]+>')
WHITESPACE_RE = re.compile(r'\s+')
SKIP_PUNCTUATION_BY_TAG = {
    'hw': ('.', ',', '—', '(', ')', ':', ';', '['),
    't': ('.',),
    'ex': ('—'),
}


@dataclass
class Block:
    tag: str
    open_start: int
    open_end: int
    close_start: int | None = None
    close_end: int | None = None


@dataclass
class Candidate:
    open_start: int
    open_end: int
    close_start: int
    close_end: int
    punct_end: int
    tag: str
    punctuation: str
    group_members: tuple = ()
    d_block: Block | None = None
    entry_block: Block | None = None


def _is_punctuation(char):
    return unicodedata.category(char).startswith(PUNCTUATION_CATEGORY_PREFIX)


def _has_source_separator(punctuation):
    return any(char in SOURCE_SEPARATORS for char in punctuation)


def _split_punctuation(punctuation, tag):
    if tag not in DASH_SPLIT_TAGS:
        return punctuation, ''
    dash = punctuation.find('—')
    if dash == -1:
        return punctuation, ''
    return punctuation[:dash], punctuation[dash:]


def _pop_opening(stack, name):
    for depth in range(len(stack) - 1, -1, -1):
        if stack[depth].tag == name:
            block = stack[depth]
            del stack[depth:]
            return block
    return None


def _should_skip(candidate, text):
    if candidate.group_members and len(candidate.group_members) > 1:
        return False
    if candidate.tag in SKIP_TAGS:
        return True
    if candidate.tag == 'src':
        if candidate.punctuation.startswith('—'):
            return True
        content = text[candidate.open_end:candidate.close_start]
        if BOLD_TAG_RE.search(content):
            return True
    if candidate.tag == 'g':
        return candidate.punctuation.startswith('—')
    skip_punctuation = SKIP_PUNCTUATION_BY_TAG.get(candidate.tag)
    if skip_punctuation is None:
        return False
    return candidate.punctuation.startswith(skip_punctuation)


def _source_group(text, candidates, start):
    first = candidates[start]
    if first.tag != 'src' or not _has_source_separator(first.punctuation):
        return None
    members = [first]
    scan = first.punct_end
    while True:
        match = SRC_ELEMENT_RE.search(text, scan)
        if match is None:
            break
        previous = members[-1]
        if text[previous.punct_end:match.start()].strip():
            break
        open_end = text.index('>', match.start()) + 1
        close_start = match.end() - len('</src>')
        close_end = match.end()
        punct_end = close_end
        while punct_end < len(text) and _is_punctuation(text[punct_end]):
            punct_end += 1
        member = Candidate(
            match.start(), open_end, close_start, close_end, punct_end,
            'src', text[close_end:punct_end],
            d_block=first.d_block, entry_block=first.entry_block,
        )
        members.append(member)
        if not _has_source_separator(member.punctuation):
            break
        scan = punct_end
    if len(members) < 2:
        return None
    group_start = first.open_start
    prefix_start = group_start
    while prefix_start > 0 and text[prefix_start - 1].isspace():
        prefix_start -= 1
    if prefix_start > 0 and text[prefix_start - 1] == '(':
        group_start = prefix_start - 1
    last = members[-1]
    group_members = tuple(
        (
            member.open_start, member.open_end, member.close_start,
            member.close_end, member.punct_end,
        )
        for member in members
    )
    group = Candidate(
        group_start, first.open_end, last.close_start, last.close_end,
        last.punct_end, 'src', last.punctuation, group_members,
        first.d_block, first.entry_block,
    )
    consumed = {member.open_start for member in members}
    return group, consumed


def _paren_source_group(text, candidate):
    if candidate.tag != 'src' or candidate.group_members:
        return None
    if not candidate.punctuation.startswith(')'):
        return None
    prefix_start = candidate.open_start
    while prefix_start > 0 and text[prefix_start - 1].isspace():
        prefix_start -= 1
    if prefix_start == 0 or text[prefix_start - 1] != '(':
        return None
    member = (
        candidate.open_start, candidate.open_end, candidate.close_start,
        candidate.close_end, candidate.punct_end,
    )
    return Candidate(
        prefix_start - 1, candidate.open_end, candidate.close_start,
        candidate.close_end, candidate.punct_end, 'src',
        candidate.punctuation, (member,), candidate.d_block,
        candidate.entry_block,
    )


def _merge_source_groups(text, candidates):
    merged = []
    index = 0
    while index < len(candidates):
        result = _source_group(text, candidates, index)
        if result is None:
            paren_group = _paren_source_group(text, candidates[index])
            merged.append(paren_group or candidates[index])
            index += 1
            continue
        group, consumed = result
        merged.append(group)
        index += 1
        while (
            index < len(candidates)
            and candidates[index].open_start in consumed
        ):
            index += 1
    return merged


def find_candidates(text):
    stack = []
    candidates = []
    for match in TOKEN_RE.finditer(text):
        name = match.group('name')
        if name is None:
            continue
        body = match.group('body') or ''
        if match.group('close'):
            block = _pop_opening(stack, name)
            if block is None:
                continue
            block.close_start = match.start()
            block.close_end = match.end()
            punct_end = match.end()
            while punct_end < len(text) and _is_punctuation(text[punct_end]):
                punct_end += 1
            if punct_end == match.end():
                continue
            d_block = next(
                (frame for frame in reversed(stack) if frame.tag == 'd'), None,
            )
            entry_block = next(
                (frame for frame in reversed(stack) if frame.tag == 'entry'),
                None,
            )
            candidates.append(Candidate(
                block.open_start, block.open_end, match.start(), match.end(),
                punct_end, name, text[match.end():punct_end],
                d_block=d_block, entry_block=entry_block,
            ))
            continue
        if body.rstrip().endswith('/'):
            continue
        stack.append(Block(name, match.start(), match.end()))
    candidates = _merge_source_groups(text, candidates)
    return [
        candidate for candidate in candidates
        if not _should_skip(candidate, text)
    ]


def _map_offset(offset, edits):
    shift = 0
    for start, end, replacement in edits:
        if end <= offset:
            shift += len(replacement) - (end - start)
    return offset + shift


def _strip_tags(fragment):
    return WHITESPACE_RE.sub(
        ' ', unescape(TAG_MARKUP_RE.sub('', fragment)),
    ).strip()


def _nested_d_ranges(text, block):
    end = block.close_end if block.close_end is not None else len(text)
    base = 1 if block.tag == 'd' else 0
    depth = 0
    ranges = []
    range_start = None
    for match in TOKEN_RE.finditer(text, block.open_start, end):
        name = match.group('name')
        if name != 'd':
            continue
        if match.group('close'):
            depth -= 1
            if depth == base and range_start is not None:
                ranges.append((range_start, match.end()))
                range_start = None
            continue
        body = match.group('body') or ''
        if body.rstrip().endswith('/'):
            continue
        depth += 1
        if depth == base + 1:
            range_start = match.start()
    return ranges


def _headwords_in_span(text, block):
    if block is None:
        return []
    end = block.close_end if block.close_end is not None else len(text)
    nested = _nested_d_ranges(text, block)
    headwords = []
    for match in HEADWORD_RE.finditer(text, block.open_start, end):
        if any(start <= match.start() < stop for start, stop in nested):
            continue
        headword = _strip_tags(match.group(1))
        if headword and headword not in headwords:
            headwords.append(headword)
    return headwords


def _candidate_headwords(text, candidate, edits=()):
    block = candidate.d_block or candidate.entry_block
    if block is None:
        return []
    mapped = Block(
        block.tag,
        _map_offset(block.open_start, edits),
        _map_offset(block.open_end, edits),
        _map_offset(block.close_start, edits)
        if block.close_start is not None else None,
        _map_offset(block.close_end, edits)
        if block.close_end is not None else None,
    )
    return _headwords_in_span(text, mapped)


def current_span(text, candidate, edits):
    return (
        _map_offset(candidate.open_start, edits),
        _map_offset(candidate.close_start, edits),
        _map_offset(candidate.close_end, edits),
        _map_offset(candidate.punct_end, edits),
    )


def _render_source_group(text, members):
    first_start = members[0][0]
    prefix_start = first_start
    scan = first_start
    while scan > 0 and text[scan - 1].isspace():
        scan -= 1
    if scan > 0 and text[scan - 1] == '(':
        prefix_start = scan - 1
    parts = [text[prefix_start:first_start]]
    for position, member in enumerate(members):
        _, open_end, close_start, close_end, punct_end = member
        parts.append(text[open_end:close_start])
        if position + 1 < len(members):
            next_open_start = members[position + 1][0]
            parts.append(text[close_end:punct_end])
            parts.append(text[punct_end:next_open_start])
    last = members[-1]
    absorbed, rest = _split_punctuation(text[last[3]:last[4]], 'src')
    parts.append(absorbed)
    return '<src>' + ''.join(parts) + '</src>' + rest


def prepared_after(text, candidate, edits):
    if candidate.group_members:
        members = [
            tuple(_map_offset(offset, edits) for offset in member)
            for member in candidate.group_members
        ]
        return _render_source_group(text, members)
    start, close_start, close_end, end = current_span(text, candidate, edits)
    absorbed, rest = _split_punctuation(
        text[close_end:end], candidate.tag,
    )
    return (
        text[start:close_start]
        + absorbed
        + text[close_start:close_end]
        + rest
    )


def apply_change(text, candidate, edits, replacement):
    start, _, _, end = current_span(text, candidate, edits)
    text = text[:start] + replacement + text[end:]
    edits = [
        edit for edit in edits
        if not (
            edit[0] >= candidate.open_start
            and edit[1] <= candidate.punct_end
        )
    ]
    edits.append((candidate.open_start, candidate.punct_end, replacement))
    return text, edits


def clip(fragment, limit=FRAGMENT_MAX):
    if len(fragment) <= limit:
        return fragment
    head = limit // 2
    tail = limit - head - 1
    return fragment[:head] + '…' + fragment[-tail:]


def iter_xml_files(paths):
    for path in paths:
        path = Path(path)
        if path.is_dir():
            yield from sorted(path.rglob('*.xml'))
        elif path.is_file():
            yield path


def read_preserving_newlines(path):
    with open(path, 'r', encoding='utf-8', newline='') as file:
        return file.read()


def write_preserving_newlines(path, text):
    with open(path, 'w', encoding='utf-8', newline='') as file:
        file.write(text)


def write_if_unchanged(path, text, expected):
    if read_preserving_newlines(path) != expected:
        return False
    write_preserving_newlines(path, text)
    return True


def is_interactive():
    try:
        return sys.stdin.isatty()
    except (AttributeError, ValueError):
        return False


def ask_action():
    try:
        answer = input(
            '  Enter = skip | y = write after | '
            'custom text = replace the whole span: '
        )
    except (EOFError, KeyboardInterrupt):
        print()
        return None
    return answer


def main(argv=None):
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    parser = argparse.ArgumentParser(
        description='Move punctuation that follows a closing tag inside it.'
    )
    parser.add_argument(
        'paths', nargs='*', default=[str(DEFAULT_PATH)],
        help='XML files or directories (default: dictionary_app/data)',
    )
    parser.add_argument(
        '--apply', action='store_true',
        help='write the prepared text for every candidate without asking',
    )
    args = parser.parse_args(argv)

    interactive = is_interactive()
    preview_only = not args.apply and not interactive
    total_candidates = 0
    written = 0
    stopped = False
    for path in iter_xml_files(args.paths):
        text = read_preserving_newlines(path)
        expected = text
        candidates = find_candidates(text)
        if not candidates:
            continue
        print(f'\n{path}')
        if any(candidate.tag in IDENTITY_TAGS for candidate in candidates):
            print(
                '  note: moving punctuation inside <hw>/<see> changes its '
                'identity; skip unless intended'
            )
        edits = []
        for index, candidate in enumerate(candidates, 1):
            total_candidates += 1
            start, _, _, end = current_span(
                text, candidate, edits,
            )
            before = text[start:end]
            after = prepared_after(text, candidate, edits)
            print(f'  [{index}/{len(candidates)}] </{candidate.tag}>')
            headwords = _candidate_headwords(text, candidate, edits)
            if headwords:
                print(f'  headword(s): {clip(", ".join(headwords))}')
            print(f'  before: {clip(before)}')
            print(f'  after:  {clip(after)}')
            print(f'  punctuation: {candidate.punctuation}')
            if preview_only:
                continue
            if args.apply:
                replacement = after
            else:
                answer = ask_action()
                if answer is None:
                    print('No input available: stopped before the next candidate.')
                    stopped = True
                    break
                if answer == '':
                    continue
                replacement = after if answer.strip().lower() == YES_ANSWER else answer
            text, edits = apply_change(
                text, candidate, edits, replacement,
            )
            if not write_if_unchanged(path, text, expected):
                print(
                    f'  {path} changed on disk; not writing. '
                    'Rerun to use the current file.'
                )
                stopped = True
                break
            expected = text
            written += 1
        if stopped:
            break

    print(f'{total_candidates} candidate(s), {written} written')
    if preview_only and total_candidates:
        print(
            'Nothing was written. Run in an interactive terminal to answer '
            'each candidate, or pass --apply to write the prepared text.'
        )
    return 0


if __name__ == '__main__':
    sys.exit(main())
