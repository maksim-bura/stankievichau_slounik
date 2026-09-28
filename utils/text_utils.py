import re


_ACCENTED_VOWEL_RE = re.compile('([аеіоуыэюя])([\u0300\u0301]+)')


def remove_accents(text):
    if not text:
        return text
    return _ACCENTED_VOWEL_RE.sub(r'\1', text)


def normalize_jo_to_je(text):
    if not text:
        return text
    return text.replace('ё', 'е').replace('Ё', 'Е')


_BY_ALPHABET = 'абвгґдеёжзійклмнопрстуўфхцчшыьэюя'


_COMBINING_ACCENT_ORDS = {0x0300, 0x0301}
_SEPARATOR_RANKS = {'-': 0, ' ': 1, '|': 1}
_LETTER_OFFSET = 2


def alphabet_sort_key(text):
    if not text:
        return []
    lowered = text.lower()
    ranks = {ch: _LETTER_OFFSET + i for i, ch in enumerate(_BY_ALPHABET)}
    key = []
    for ch in lowered:
        if ch in _SEPARATOR_RANKS:
            key.append(_SEPARATOR_RANKS[ch])
            continue
        if ord(ch) in _COMBINING_ACCENT_ORDS:
            continue
        key.append(ranks.get(ch, _LETTER_OFFSET + len(_BY_ALPHABET) + ord(ch)))
    return key