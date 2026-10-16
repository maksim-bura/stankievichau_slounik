import re


_APOS = "'\u2019\u02BC"
_ACCENT_CLASS = r'\u0300\u0301'
_WORD_CHARS = r'\w' + _ACCENT_CLASS + _APOS + r'-'
_WORD_START = r'(?<![' + _WORD_CHARS + r'])'
_WORD_END = r'(?![' + _WORD_CHARS + r'])'
_ACCENT_COMB = r'(?:[\u0300\u0301])?'
_ACCENT_COMB_REQUIRED = r'(?:[\u0300\u0301])+'
_ACCENT_ORDS = {0x0300, 0x0301}


def _char_part(ch, required):
    if ch == '*':
        return r'[' + _WORD_CHARS + r']+'
    if ch == '?':
        return r'[' + _WORD_CHARS + r']'
    if ch.isupper():
        base = re.escape(ch)
    elif ch.islower() and ch.upper() != ch:
        base = f'[{re.escape(ch)}{re.escape(ch.upper())}]'
    else:
        base = re.escape(ch)
    return base + (_ACCENT_COMB_REQUIRED if required else _ACCENT_COMB)


def _plain_word_pattern(word):
    parts = []
    has_wildcard = False
    for ch in word:
        if ch in ('*', '?'):
            has_wildcard = True
        parts.append(_char_part(ch, False))
    word_pattern = _WORD_START + ''.join(parts)
    return word_pattern, has_wildcard


def _accented_word_pattern(word):
    parts = []
    has_wildcard = False
    i = 0
    length = len(word)
    while i < length:
        ch = word[i]
        if ord(ch) in _ACCENT_ORDS:
            i += 1
            continue
        j = i + 1
        required = False
        while j < length and ord(word[j]) in _ACCENT_ORDS:
            required = True
            j += 1
        if ch in ('*', '?'):
            has_wildcard = True
        parts.append(_char_part(ch, required))
        i = j
    word_pattern = _WORD_START + ''.join(parts)
    return word_pattern, has_wildcard


def compile_search_regex(search_text, exact_words=False):
    words = search_text.split()
    word_patterns = []
    for word in words:
        if any(ord(ch) in _ACCENT_ORDS for ch in word):
            word_pattern, has_wildcard = _accented_word_pattern(word)
        else:
            word_pattern, has_wildcard = _plain_word_pattern(word)
        if has_wildcard or exact_words:
            word_pattern += _WORD_END
        word_patterns.append(word_pattern)
    return re.compile(r'\s+'.join(word_patterns), re.UNICODE)