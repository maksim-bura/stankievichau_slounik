import re


_ACCENTED_VOWEL_RE = re.compile('([аеіоуыэюя])([\u0300\u0301]+)')


def remove_accents(text):
    if not text:
        return text
    return _ACCENTED_VOWEL_RE.sub(r'\1', text)


def collapse_same_entry_duplicates(results):
    """Collapse duplicate rows that live in the SAME entry.

    Two rows are a same-entry duplicate when they share the DB entry id
    (``result[0]``) and the accent-stripped headword (``result[1]``). Genuine
    homonyms share a headword but have different ids, so they are kept. The
    first occurrence wins, preserving the caller's ordering.
    """
    seen = set()
    collapsed = []
    for result in results:
        key = (result[0], remove_accents(result[1]))
        if key in seen:
            continue
        seen.add(key)
        collapsed.append(result)
    return collapsed


def normalize_jo_to_je(text):
    if not text:
        return text
    return text.replace('ё', 'е').replace('Ё', 'Е')


_BY_ALPHABET = 'абвгґдеёжзійклмнопрстуўфхцчшыьэюя'


_COMBINING_ACCENT_ORDS = {0x0300, 0x0301}
_SEPARATOR_RANKS = {'-': 0, ' ': 1, '|': 1}
_LETTER_OFFSET = 2


_SORT_IGNORED_CHAR_ORDS = {0x27, 0x2019, 0x02BC}


def alphabet_sort_key(text):
    if not text:
        return [], []
    ranks = {ch: _LETTER_OFFSET + i for i, ch in enumerate(_BY_ALPHABET)}
    rank_list = []
    case_flags = []
    for ch in text:
        ch_lower = ch.lower()
        if ch_lower in _SEPARATOR_RANKS:
            rank_list.append(_SEPARATOR_RANKS[ch_lower])
            case_flags.append(0)
            continue
        if ord(ch) in _COMBINING_ACCENT_ORDS or ord(ch) in _SORT_IGNORED_CHAR_ORDS:
            continue
        rank_list.append(ranks.get(ch_lower, _LETTER_OFFSET + len(_BY_ALPHABET) + ord(ch)))
        case_flags.append(0 if ch_lower == ch else 1)
    return rank_list, case_flags