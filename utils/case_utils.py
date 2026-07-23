import re


_APOS = "'\u2019\u02BC"
_WORD_CHARS = r'\w' + _APOS + r'-'
_WORD_START = r'(?<![' + _WORD_CHARS + r'])'
_WORD_END = r'(?![' + _WORD_CHARS + r'])'
_ACCENT_COMB = r'(?:[\u0300\u0301])?'


def compile_search_regex(search_text, exact_words=False):
    words = search_text.split()
    word_patterns = []
    for word in words:
        parts = []
        has_wildcard = False
        for i, ch in enumerate(word):
            if ch == '*':
                has_wildcard = True
                parts.append(r'[' + _WORD_CHARS + r']+')
            elif ch == '?':
                has_wildcard = True
                parts.append(r'[' + _WORD_CHARS + r']')
            elif ch.isupper():
                parts.append(re.escape(ch) + _ACCENT_COMB)
            elif ch.islower():
                upper = ch.upper()
                if upper != ch:
                    parts.append(f'[{re.escape(ch)}{re.escape(upper)}]{_ACCENT_COMB}')
                else:
                    parts.append(re.escape(ch) + _ACCENT_COMB)
            else:
                parts.append(re.escape(ch) + _ACCENT_COMB)
        word_pattern = ''.join(parts)
        word_pattern = _WORD_START + word_pattern
        if has_wildcard or exact_words:
            word_pattern += _WORD_END
        word_patterns.append(word_pattern)
    return re.compile(r'\s+'.join(word_patterns), re.UNICODE)
