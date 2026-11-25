import argparse
import json
import re
import sys
import unicodedata
from dataclasses import dataclass
from html import unescape
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = TOOLS_DIR.parent
DEFAULT_PATH = PROJECT_ROOT / 'dictionary_app' / 'data'

PROHIBITED_PAIRS = [
]

FORGOT_PATH = TOOLS_DIR / 'fix_tag_punctuation_forget.json'

WRITE_PREFIX = 'write: '

FORGET_ANSWER = 'forget'

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
SKIPPED_FILES = {'sources.xml'}
SRC_ELEMENT_RE = re.compile(r'<src(?:\s[^>]*)?>.*?</src>', re.DOTALL)
G_ELEMENT_RE = re.compile(r'<g>.*?</g>', re.DOTALL)
POD_SEE_RE = re.compile(r'под\s+<see\b[^>]*>.*?</see>', re.DOTALL)
CLOSING_RUN_RE = re.compile(r'(?:</[A-Za-z_][\w:.-]*>)+$')
INNER_CLOSING_RE = re.compile(r'</(?P<name>[A-Za-z_][\w:.-]*)>')
HEADWORD_RE = re.compile(r'<hw\b[^>]*>(.*?)</hw>', re.DOTALL)
TAG_MARKUP_RE = re.compile(r'<[^>]+>')
WHITESPACE_RE = re.compile(r'\s+')
SRC_BOLD_ONLY_RE = re.compile(r'<b>С\.</b>')
SKIP_PUNCTUATION_BY_TAG = {
    'hw': ('.', ',', ')', '(', '—', ':', '[', ';'),
    't': ('.',),
    'src': ('(',),
}
T_PERIOD_SUFFIXES = ('-л', '-н', 'т.п')


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
    dash_inside: bool = False


def _is_punctuation(char):
    return unicodedata.category(char).startswith(PUNCTUATION_CATEGORY_PREFIX)


def _split_punctuation(punctuation):
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


def _src_close_in_run(text, close_start):
    run = CLOSING_RUN_RE.search(text, 0, close_start)
    if run is None or run.end() != close_start:
        return None
    target = None
    for closing in INNER_CLOSING_RE.finditer(text, run.start(), run.end()):
        if closing.group('name') == 'src':
            target = closing.start()
    return target

def _has_outer_open_paren(text, candidate):
    scan = candidate.open_start
    depth = 0
    while scan > 0:
        char = text[scan - 1]
        if char in '\r\n':
            return False
        if char == ')':
            depth += 1
        elif char == '(':
            if depth == 0:
                return True
            depth -= 1
        scan -= 1
    return False


def _should_skip(candidate, text):
    if candidate.group_members and len(candidate.group_members) > 1:
        return False
    if candidate.tag in SKIP_TAGS:
        return True
    if candidate.dash_inside:
        return candidate.tag in IDENTITY_TAGS
    if candidate.tag == 'i' and candidate.punctuation.startswith(').'):
        content = text[candidate.open_end:candidate.close_start].strip()
        if POD_SEE_RE.fullmatch(content):
            return True
    if candidate.tag == 'src':
        content = text[candidate.open_end:candidate.close_start].strip()
        if SRC_BOLD_ONLY_RE.fullmatch(content):
            return True
        if (
            candidate.punctuation.startswith(')')
            and _has_outer_open_paren(text, candidate)
        ):
            return True
    if candidate.tag == 't' and candidate.punctuation.startswith('.'):
        content = _strip_tags(text[candidate.open_end:candidate.close_start])
        if content.endswith(T_PERIOD_SUFFIXES):
            return False
    skip_punctuation = SKIP_PUNCTUATION_BY_TAG.get(candidate.tag)
    if skip_punctuation is None:
        return False
    return candidate.punctuation.startswith(skip_punctuation)


def _punct_end(text, pos):
    end = pos
    while end < len(text) and _is_punctuation(text[end]):
        end += 1
    return end


def _dash_inside_start(text, close_start):
    start = close_start
    while start > 0 and _is_punctuation(text[start - 1]):
        start -= 1
    if '—' not in text[start:close_start]:
        return None
    return start


def _is_element_separator(gap):
    if any(
        not (char.isspace() or _is_punctuation(char)) for char in gap
    ):
        return False
    punctuation = [char for char in gap if _is_punctuation(char)]
    return not punctuation or any(char in ';,' for char in punctuation)


def _element_runs(text, pattern):
    runs = []
    current = []
    for match in pattern.finditer(text):
        if current and _is_element_separator(
                text[current[-1].end():match.start()]):
            current.append(match)
        else:
            if len(current) > 1:
                runs.append(current)
            current = [match]
    if len(current) > 1:
        runs.append(current)
    return runs


def _block_close(text, block):
    depth = 0
    for match in TOKEN_RE.finditer(text, block.open_end):
        name = match.group('name')
        if name is None or name != block.tag:
            continue
        if match.group('close'):
            if depth == 0:
                return match.start(), match.end()
            depth -= 1
            continue
        body = match.group('body') or ''
        if not body.rstrip().endswith('/'):
            depth += 1
    return None


def _enclosing_blocks(text, pos):
    stack = []
    for match in TOKEN_RE.finditer(text, 0, pos):
        name = match.group('name')
        if name is None:
            continue
        if match.group('close'):
            _pop_opening(stack, name)
            continue
        body = match.group('body') or ''
        if body.rstrip().endswith('/'):
            continue
        stack.append(Block(name, match.start(), match.end()))
    found = {}
    for frame in reversed(stack):
        if frame.tag not in ('d', 'entry') or frame.tag in found:
            continue
        close = _block_close(text, frame)
        if close is not None:
            frame.close_start, frame.close_end = close
        found[frame.tag] = frame
    return found.get('d'), found.get('entry')


def _element_group_candidates(text, pattern, tag):
    groups = []
    for matches in _element_runs(text, pattern):
        members = tuple(
            (
                match.start(), text.index('>', match.start()) + 1,
                match.end() - len('</' + tag + '>'), match.end(),
                _punct_end(text, match.end()),
            )
            for match in matches
        )
        d_block, entry_block = _enclosing_blocks(text, matches[0].start())
        group_start = matches[0].start()
        if tag == 'src':
            prefix_start = group_start
            while prefix_start > 0 and text[prefix_start - 1].isspace():
                prefix_start -= 1
            if prefix_start > 0 and text[prefix_start - 1] == '(':
                group_start = prefix_start - 1
        groups.append(Candidate(
            group_start, members[0][1], members[-1][2], members[-1][3],
            members[-1][4], tag, text[members[-1][3]:members[-1][4]],
            members, d_block, entry_block,
        ))
    return groups


def _merge_element_groups(text, candidates):
    groups = (
        _element_group_candidates(text, SRC_ELEMENT_RE, 'src')
        + _element_group_candidates(text, G_ELEMENT_RE, 'g')
    )
    if not groups:
        return candidates
    candidates = [
        candidate for candidate in candidates
        if not any(
            candidate.open_start in {
                member[0] for member in group.group_members
            }
            or (
                group.open_start <= candidate.open_start
                and candidate.close_end <= group.close_end
            )
            for group in groups
        )
    ]
    for group in groups:
        insert_at = next(
            (
                index for index, candidate in enumerate(candidates)
                if candidate.open_start > group.open_start
            ),
            len(candidates),
        )
        candidates.insert(insert_at, group)
    return candidates


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
            punct_end = _punct_end(text, match.end())
            d_block = next(
                (frame for frame in reversed(stack) if frame.tag == 'd'),
                None,
            )
            entry_block = next(
                (frame for frame in reversed(stack) if frame.tag == 'entry'),
                None,
            )
            if punct_end > match.end():
                close_start = match.start()
                tag_name = name
                src_close = _src_close_in_run(text, close_start)
                if src_close is not None:
                    close_start = src_close
                    tag_name = 'src'
                candidates.append(Candidate(
                    block.open_start, block.open_end, close_start, match.end(),
                    punct_end, tag_name, text[match.end():punct_end],
                    d_block=d_block, entry_block=entry_block,
                ))
            dash_start = _dash_inside_start(text, match.start())
            if dash_start is not None:
                candidates.append(Candidate(
                    block.open_start, block.open_end, match.start(),
                    match.end(), match.end(), name,
                    text[dash_start:match.start()],
                    d_block=d_block, entry_block=entry_block,
                    dash_inside=True,
                ))
            continue
        if body.rstrip().endswith('/'):
            continue
        stack.append(Block(name, match.start(), match.end()))
    candidates = _merge_element_groups(text, candidates)
    kept = []
    for candidate in candidates:
        candidate = _paren_source_group(text, candidate) or candidate
        if _should_skip(candidate, text):
            continue
        start, _, _, end = current_span(text, candidate, [])
        if prepared_after(text, candidate, []) == text[start:end]:
            continue
        kept.append(candidate)
    return kept


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
    absorbed, rest = _split_punctuation(text[last[3]:last[4]])
    parts.append(absorbed)
    opening = text[members[0][0]:members[0][1]]
    return opening + ''.join(parts) + '</src>' + rest


def _render_g_group(text, members):
    parts = []
    for position, member in enumerate(members):
        _, open_end, close_start, _, _ = member
        if position:
            parts.append(text[members[position - 1][3]:member[0]])
        parts.append(text[open_end:close_start])
    last = members[-1]
    opening = text[members[0][0]:members[0][1]]
    return opening + ''.join(parts) + '</g>' + text[last[3]:last[4]]


def prepared_after(text, candidate, edits):
    if candidate.group_members:
        members = [
            tuple(_map_offset(offset, edits) for offset in member)
            for member in candidate.group_members
        ]
        if candidate.tag == 'g':
            return _render_g_group(text, members)
        return _render_source_group(text, members)
    start, close_start, close_end, end = current_span(text, candidate, edits)
    if candidate.dash_inside:
        keep, outside = _split_punctuation(candidate.punctuation)
        return (
            text[start:close_start - len(candidate.punctuation)]
            + keep
            + text[close_start:close_end]
            + outside
        )
    absorbed, rest = _split_punctuation(text[close_end:end])
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
            found = sorted(path.rglob('*.xml'))
        elif path.is_file():
            found = [path]
        else:
            found = []
        for file in found:
            if file.name.lower() in SKIPPED_FILES:
                print(f'\n{file}\n  skipped: source-list file, no entries')
                continue
            yield file


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


def _headword_scope(headwords):
    return tuple(sorted({headword for headword in headwords if headword}))


def load_forgotten_pairs(path):
    try:
        with open(path, 'r', encoding='utf-8') as file:
            data = json.load(file)
    except FileNotFoundError:
        return set()
    except (OSError, ValueError):
        print(f'  warning: cannot read {path}; ignored.')
        return set()
    pairs = set()
    entries = data.get('forgotten', []) if isinstance(data, dict) else []
    for entry in entries:
        if not isinstance(entry, (list, tuple)) or len(entry) not in (2, 3):
            continue
        before, after = str(entry[0]), str(entry[1])
        if len(entry) == 3 and entry[2]:
            scope = _headword_scope(
                [str(head) for head in entry[2] if str(head).strip()]
            )
        else:
            scope = ()
        pairs.add((before, after, scope))
    return pairs


def save_forgotten_pairs(path, pairs):
    data = {
        'forgotten': [
            [before, after, list(scope)]
            for before, after, scope in sorted(pairs)
        ]
    }
    with open(path, 'w', encoding='utf-8') as file:
        json.dump(data, file, ensure_ascii=False, indent=2)
        file.write('\n')


def _is_forgotten(pair, headwords, forgotten):
    before, after = pair
    if (before, after, ()) in forgotten:
        return True
    return (before, after, _headword_scope(headwords)) in forgotten


def ask_action():
    try:
        answer = input(
            '  Enter = skip | y = write after | '
            'forget = hide for these headword(s) | '
            'write: <text> = replace the span: '
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
    prohibited = {tuple(pair) for pair in PROHIBITED_PAIRS}
    forgotten = load_forgotten_pairs(FORGOT_PATH)
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
            start, _, _, end = current_span(
                text, candidate, edits,
            )
            before = text[start:end]
            after = prepared_after(text, candidate, edits)
            pair = (clip(before), clip(after))
            headwords = _candidate_headwords(text, candidate, edits)
            if pair in prohibited:
                continue
            if _is_forgotten(pair, headwords, forgotten):
                continue
            total_candidates += 1
            print(f'  [{index}/{len(candidates)}] </{candidate.tag}>')
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
                replacement = None
                while True:
                    answer = ask_action()
                    if answer is None:
                        print(
                            'No input available: stopped before the next '
                            'candidate.'
                        )
                        stopped = True
                        break
                    stripped = answer.strip()
                    lowered = stripped.lower()
                    if not stripped:
                        break
                    if lowered == YES_ANSWER:
                        replacement = after
                        break
                    if lowered == FORGET_ANSWER:
                        scope = _headword_scope(headwords)
                        forgotten.add((pair[0], pair[1], scope))
                        save_forgotten_pairs(FORGOT_PATH, forgotten)
                        if scope:
                            print(
                                '  forgotten for headword(s): '
                                f'{", ".join(scope)} '
                                '(other headwords still shown).'
                            )
                        else:
                            print(
                                '  forgotten globally '
                                '(no enclosing headword found).'
                            )
                        break
                    if answer.startswith(WRITE_PREFIX):
                        custom = answer[len(WRITE_PREFIX):]
                        if custom.strip():
                            replacement = custom
                            break
                        print(
                            f'  nothing after "{WRITE_PREFIX}"; '
                            'nothing was written.'
                        )
                        continue
                    print(
                        '  not written: use Enter to skip, '
                        f'"{YES_ANSWER}" to accept, "{FORGET_ANSWER}", '
                        f'or "{WRITE_PREFIX}" followed by your text.'
                    )
                if stopped:
                    break
                if replacement is None:
                    continue
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