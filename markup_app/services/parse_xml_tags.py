import re

from dictionary_app.utils.normalize_headword import has_keep_acc, resolve_headword
from markup_app.utils.constants import LINK_PLACEHOLDER


_TAG_RE = re.compile(r'<(/?)(?:' + LINK_PLACEHOLDER + r')?(\w+)[^>]*>')
_ENTRY_OPEN_RE = re.compile(
    r'<(?:' + LINK_PLACEHOLDER + r')?entry\b[^>]*>'
)
_ENTRY_CLOSE_RE = re.compile(r'</entry\s*>')
_HW_TEXT_RE = re.compile(
    r'<(?:' + LINK_PLACEHOLDER + r')?hw\b([^>]*)>(.*?)</hw>', re.DOTALL
)
_NAME_CHAR_RE = re.compile(r'[A-Za-z0-9_]')


def is_name_char(ch):
    return len(ch) == 1 and _NAME_CHAR_RE.fullmatch(ch) is not None


def placeholder_positions(text):
    return [match.start() for match in re.finditer(LINK_PLACEHOLDER, text)]


def placeholder_clean_starts(positions):
    return [position - 1 - 2 * index for index, position in enumerate(positions)]


def scan_tags(text):
    tags = []
    i = 0
    n = len(text)
    while i < n:
        lt = text.find('<', i)
        if lt < 0:
            break
        gt = text.find('>', lt + 1)
        if gt < 0:
            break
        closing = text[lt + 1:lt + 2] == '/'
        ns = lt + (2 if closing else 1)
        if not closing and text[ns:ns + 2] == LINK_PLACEHOLDER:
            ns += 2
        ne = ns
        while ne < gt and is_name_char(text[ne]):
            ne += 1
        inner = text[lt + 1:gt]
        if ne == ns and inner not in ('', '/'):
            i = lt + 1
            continue
        tags.append({
            'start': lt,
            'end': gt + 1,
            'name_start': ns,
            'name_end': ne,
            'closing': closing,
            'self_closing': (not closing) and inner.rstrip().endswith('/'),
            'name': text[ns:ne],
        })
        i = gt + 1
    return tags


def partner_tag(tags, edited):
    stack = []
    for tag in tags:
        if tag['self_closing']:
            continue
        if tag['closing']:
            for j in range(len(stack) - 1, -1, -1):
                if stack[j]['name'] == tag['name']:
                    open_tag = stack.pop(j)
                    if open_tag is edited:
                        return tag
                    if tag is edited:
                        return open_tag
                    break
        else:
            stack.append(tag)
    return None


def is_inside_tag(text, pos):
    for m in _TAG_RE.finditer(text):
        if m.start() < pos < m.end():
            return True
    return False


def _build_tag_dicts(text):
    tags = []
    for m in _TAG_RE.finditer(text):
        raw = text[m.start():m.end()]
        tags.append({
            'start': m.start(),
            'end': m.end(),
            'name': m.group(2),
            'closing': m.group(1) == '/',
            'self_closing': raw.endswith('/>'),
        })
    return tags


def _find_tag_pair_at_boundary(text, char_pos):
    tags = _build_tag_dicts(text)

    stack = []
    for tag in tags:
        if tag['closing']:
            for i in range(len(stack) - 1, -1, -1):
                if stack[i]['name'] == tag['name']:
                    open_tag = stack.pop(i)
                    if _tag_delimiter_at_boundary(open_tag, tag, char_pos):
                        return open_tag, tag
                    break
            else:
                if char_pos == tag['start'] or char_pos == tag['end'] - 1:
                    return tag, tag
        else:
            if tag['self_closing'] and (
                char_pos == tag['start'] or char_pos == tag['end'] - 1
            ):
                return tag, tag
            stack.append(tag)
    for open_tag in stack:
        if open_tag['self_closing']:
            continue
        if char_pos == open_tag['start'] or char_pos == open_tag['end'] - 1:
            return open_tag, open_tag
    return None, None


def find_rogue_tags(text):
    tags = _build_tag_dicts(text)
    stack = []
    rogues = []
    for tag in tags:
        if tag['self_closing']:
            continue
        if tag['closing']:
            for i in range(len(stack) - 1, -1, -1):
                if stack[i]['name'] == tag['name']:
                    stack.pop(i)
                    break
            else:
                rogues.append(tag)
        else:
            stack.append(tag)
    rogues.extend(stack)
    return rogues


def innermost_d_span(text, pos):
    tags = _build_tag_dicts(text)
    stack = []
    for tag in tags:
        if tag['self_closing']:
            continue
        if tag['closing']:
            for i in range(len(stack) - 1, -1, -1):
                if stack[i]['name'] == tag['name']:
                    open_tag = stack.pop(i)
                    if open_tag['name'] == 'd' and open_tag['start'] <= pos <= tag['end']:
                        return open_tag, tag
                    break
        else:
            stack.append(tag)
    return None, None


def find_hw_occurrences(text, headword_key):
    return [
        m for m in _HW_TEXT_RE.finditer(text)
        if resolve_headword(
            re.sub(r'<[^>]+>', '', m.group(2)).strip(),
            has_keep_acc(m.group(1)),
        ) == headword_key
    ]


def find_hw_occurrence(text, headword_key, occurrence_index):
    found = None
    k = 0
    for m in find_hw_occurrences(text, headword_key):
        if k == occurrence_index:
            return m
        found = m
        k += 1
    return found


def entry_block_span(text):
    m_open = _ENTRY_OPEN_RE.search(text)
    m_close = _ENTRY_CLOSE_RE.search(text)
    if m_open and m_close and m_close.start() > m_open.start():
        return m_open.start(), m_close.end()
    return None


def non_d_region_hw_count(text, pos):
    entry = entry_block_span(text) or (0, len(text))
    tags = _build_tag_dicts(text)
    stack = []
    spans = []
    for tag in tags:
        if tag['self_closing']:
            continue
        if tag['closing']:
            for i in range(len(stack) - 1, -1, -1):
                if stack[i]['name'] == tag['name']:
                    open_tag = stack.pop(i)
                    if open_tag['name'] == 'd':
                        spans.append((open_tag['start'], tag['end']))
                    break
        else:
            stack.append(tag)
    a, b = entry
    for s, e in spans:
        if e <= pos and e > a:
            a = e
        if s >= pos and s < b:
            b = s
    count = 0
    for m in _HW_TEXT_RE.finditer(text):
        if a <= m.start() < b:
            count += 1
    return count


def non_d_regions(text, entry_start, entry_end):
    tags = _build_tag_dicts(text)
    stack = []
    d_spans = []
    for tag in tags:
        if tag['self_closing']:
            continue
        if tag['closing']:
            for i in range(len(stack) - 1, -1, -1):
                if stack[i]['name'] == tag['name']:
                    open_tag = stack.pop(i)
                    if open_tag['name'] == 'd':
                        d_spans.append((open_tag['start'], tag['end']))
                    break
        else:
            stack.append(tag)
    open_match = _ENTRY_OPEN_RE.match(text, entry_start)
    content_start = open_match.end() if open_match else entry_start
    close_match = _ENTRY_CLOSE_RE.search(text, entry_start, entry_end)
    content_end = close_match.start() if close_match else entry_end
    regions = []
    cursor_pos = entry_start
    for span_start, span_end in sorted(d_spans):
        if span_end <= entry_start or span_start >= entry_end:
            continue
        if span_start > cursor_pos:
            regions.append((cursor_pos, span_start))
        if span_end > cursor_pos:
            cursor_pos = span_end
    if cursor_pos < entry_end:
        regions.append((cursor_pos, entry_end))
    regions = [
        (max(s, content_start), min(e, content_end))
        for s, e in regions
    ]
    return [(s, e) for s, e in regions if e > s]


def _tag_delimiter_at_boundary(open_tag, close_tag, char_pos):
    return (
        char_pos == open_tag['start']
        or char_pos == open_tag['end'] - 1
        or char_pos == close_tag['start']
        or char_pos == close_tag['end'] - 1
    )


def pair_at_deletion_boundary(text, pos, forward):
    char_pos = pos if forward else pos - 1
    if char_pos < 0 or char_pos >= len(text):
        return None, None
    ch = text[char_pos]
    if ch != '>' and ch != '<':
        return None, None
    return _find_tag_pair_at_boundary(text, char_pos)
