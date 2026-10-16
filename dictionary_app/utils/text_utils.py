import re


_ACCENTED_VOWEL_RE = re.compile('([аеіоуыэюя])([\u0300\u0301]+)')
_KEEP_ACC_ATTR_RE = re.compile(r'(?:^|\s)keep-acc(?![\w-])')


def remove_accents(text):
    if not text:
        return text
    return _ACCENTED_VOWEL_RE.sub(r'\1', text)


def resolve_headword(text, keep_acc):
    if keep_acc:
        return text
    return remove_accents(text)


def has_keep_acc(attrs_text):
    return bool(attrs_text) and _KEEP_ACC_ATTR_RE.search(attrs_text) is not None


def hw_identity(text, keep_acc):
    if keep_acc:
        return normalize_jo_to_je(text)
    return normalize_jo_to_je(remove_accents(text))


def collapse_same_entry_duplicates(results):
    seen = set()
    collapsed = []
    for result in results:
        keep_acc = result[6] if len(result) > 6 else 0
        key = (result[0], resolve_headword(result[1], keep_acc))
        if key in seen:
            continue
        seen.add(key)
        collapsed.append(result)
    return collapsed


def normalize_jo_to_je(text):
    if not text:
        return text
    return text.replace('ё', 'е').replace('Ё', 'Е')


_ENTRY_ID_SORT_RE = re.compile(r'_p(\d+)(?:_(\d+))?')


def entry_id_sort_key(entry_id):
    if not entry_id:
        return ()
    match = _ENTRY_ID_SORT_RE.search(entry_id)
    if not match:
        return ()
    first = int(match.group(1))
    second = int(match.group(2)) if match.group(2) is not None else 0
    return (first, second)


_BY_ALPHABET = 'абвгґдеёжзійклмнопрстуўфхцчшыьэюя'


_COMBINING_ACCENT_ORDS = {0x0300, 0x0301}
_SEPARATOR_RANKS = {'-': 0, ' ': 1, '|': 1}
_LETTER_OFFSET = 2


_SORT_IGNORED_CHAR_ORDS = {0x27, 0x2019, 0x02BC}


def alphabet_sort_key(text):
    if not text:
        return [], [], []
    ranks = {ch: _LETTER_OFFSET + i for i, ch in enumerate(_BY_ALPHABET)}
    rank_list = []
    case_flags = []
    accent_positions = []
    for ch in text:
        ch_lower = ch.lower()
        if ch_lower in _SEPARATOR_RANKS:
            rank_list.append(_SEPARATOR_RANKS[ch_lower])
            case_flags.append(0)
            continue
        if ord(ch) in _COMBINING_ACCENT_ORDS:
            if rank_list:
                accent_positions.append(len(rank_list) - 1)
            continue
        if ord(ch) in _SORT_IGNORED_CHAR_ORDS:
            continue
        rank_list.append(ranks.get(ch_lower, _LETTER_OFFSET + len(_BY_ALPHABET) + ord(ch)))
        case_flags.append(0 if ch_lower == ch else 1)
    return rank_list, case_flags, accent_positions