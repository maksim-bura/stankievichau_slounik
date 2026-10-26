import re

from dictionary_app.utils.remove_accents import APOSTROPHE_CHARS, COMBINING_ACUTE_MARKS

_ENTRY_ID_SORT_RE = re.compile(r'_p(\d+)(?:_(\d+))?')

_BY_ALPHABET = 'абвгґдеёжзійклмнопрстуўфхцчшыьэюя'

_COMBINING_ACCENT_ORDS = set(COMBINING_ACUTE_MARKS)
_SEPARATOR_RANKS = {'-': 0, ' ': 1, '|': 1}
_LETTER_OFFSET = 2

_SORT_IGNORED_CHAR_ORDS = set(APOSTROPHE_CHARS)

_ORDER_KEY_WIDTH = 4
_ORDER_KEY_SHIFT = 1

_LETTER_RANKS = {ch: _LETTER_OFFSET + i for i, ch in enumerate(_BY_ALPHABET)}
_UNKNOWN_LETTER_RANK = _LETTER_OFFSET + len(_BY_ALPHABET)


def entry_id_sort_key(entry_id):
    if not entry_id:
        return ()
    match = _ENTRY_ID_SORT_RE.search(entry_id)
    if not match:
        return ()
    first = int(match.group(1))
    second = int(match.group(2)) if match.group(2) is not None else 0
    return (first, second)


def encode_order_key(*sequences):
    encoded = bytearray()
    for sequence in sequences:
        for value in sequence:
            encoded += (value + _ORDER_KEY_SHIFT).to_bytes(_ORDER_KEY_WIDTH, 'big')
        encoded += b'\x00' * _ORDER_KEY_WIDTH
    return bytes(encoded)


def alphabet_sort_key(text):
    if not text:
        return [], [], []
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
        rank_list.append(_LETTER_RANKS.get(ch_lower, _UNKNOWN_LETTER_RANK + ord(ch)))
        case_flags.append(0 if ch_lower == ch else 1)
    return rank_list, case_flags, accent_positions
