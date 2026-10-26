import re


COMBINING_ACUTE_MARKS = (0x0300, 0x0301)
COMBINING_ACUTE_CLASS = ''.join('\\u%04x' % code for code in COMBINING_ACUTE_MARKS)
APOSTROPHE_CHARS = (0x27, 0x2019, 0x02BC)
APOSTROPHE_CLASS = ''.join('\\u%04x' % code for code in APOSTROPHE_CHARS)

_ACCENTED_VOWEL_RE = re.compile('([аеіоуыэюя])([' + COMBINING_ACUTE_CLASS + ']+)')


def remove_accents(text):
    if not text:
        return text
    return _ACCENTED_VOWEL_RE.sub(r'\1', text)
