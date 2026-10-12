import re

from utils.xml_schema import ATTRIBUTES, BOOL, TEXT

_NAME_RE = re.compile(r'[A-Za-z][\w.-]*')


class CompletionContext:
    __slots__ = ('tag', 'present', 'fragment')

    def __init__(self, tag, present, fragment):
        self.tag = tag
        self.present = present
        self.fragment = fragment

    def candidates(self):
        spec = ATTRIBUTES.get(self.tag)
        if not spec:
            return []
        frag = self.fragment.lower()
        return [
            (name, kind) for name, kind in spec
            if name.lower() not in self.present and name.lower().startswith(frag)
        ]


def detect_context(text, pos):
    """Return a CompletionContext when the caret sits in the attribute-name
    slot of an opening tag, else None. Never fires inside attribute values or
    inside tag content."""
    lt = text.rfind('<', 0, pos)
    if lt == -1:
        return None
    region = text[lt + 1:pos]
    if '>' in region:
        return None
    head = _NAME_RE.match(region)
    if not head:
        return None
    tag = head.group(0).lower()
    if tag not in ATTRIBUTES:
        return None
    rest = region[head.end():]
    if not rest or not rest[0].isspace():
        return None

    present = set()
    n = len(rest)
    i = 0
    while i < n:
        while i < n and rest[i].isspace():
            i += 1
        if i >= n:
            break
        if rest[i] in '/>':
            return None
        name_match = _NAME_RE.match(rest, i)
        if not name_match:
            return None
        name = name_match.group(0)
        i = name_match.end()
        j = i
        while j < n and rest[j].isspace():
            j += 1
        if j >= n:
            if j == i:
                return CompletionContext(tag, present, name)
            present.add(name.lower())
            break
        if rest[j] == '=':
            present.add(name.lower())
            i = j + 1
            while i < n and rest[i].isspace():
                i += 1
            if i >= n:
                return None
            quote = rest[i]
            if quote in '"\'':
                close = rest.find(quote, i + 1)
                if close == -1:
                    return None
                i = close + 1
            else:
                while i < n and not rest[i].isspace():
                    i += 1
                if i >= n:
                    return None
        else:
            present.add(name.lower())
            i = j
    return CompletionContext(tag, present, '')
