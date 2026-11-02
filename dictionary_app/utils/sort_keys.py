import re

from dictionary_app.utils.constants import SEP_SORT_SENTINEL
from dictionary_app.utils.remove_accents import APOSTROPHE_CHARS, COMBINING_ACUTE_MARKS


SORT_ORDER_STANDARD = 'standard'
SORT_ORDER_DICTIONARY = 'dictionary'

_BY_ALPHABET = 'абвгґдеёжзійклмнопрстуўфхцчшыьэюя'
_ALPHABET_TOKENS = {
    SORT_ORDER_STANDARD: tuple(_BY_ALPHABET),
    SORT_ORDER_DICTIONARY: (
        'о', 'а', 'э', 'б', 'г', 'ґ', 'х', 'д', 'е', 'ё', 'я',
        'дз', 'дж', 'з', 'ж', 'і', 'й', 'к', 'л', 'м', 'н', 'ф', 'п',
        'р', 'с', 'ш', 'т', 'в', 'у', 'ў', 'ь', 'ц', 'ч', 'ы', 'ю',
    ),
}

_ENTRY_ID_SORT_RE = re.compile(r'_p(\d+)(?:_(\d+))?')

_COMBINING_ACCENT_ORDS = set(COMBINING_ACUTE_MARKS)
_SEPARATOR_RANKS = {'-': 0, ' ': 1, '|': 1}
_LETTER_OFFSET = 2

_SORT_IGNORED_CHAR_ORDS = set(APOSTROPHE_CHARS)

_ORDER_KEY_WIDTH = 4
_ORDER_KEY_SHIFT = 1

_DEFAULT_TOKEN_RANKS = {
    token: _LETTER_OFFSET + index
    for index, token in enumerate(_ALPHABET_TOKENS[SORT_ORDER_STANDARD])
}
_DEFAULT_UNKNOWN_LETTER_RANK = _LETTER_OFFSET + len(_ALPHABET_TOKENS[SORT_ORDER_STANDARD])

_TOKEN_RANKS = {
    order: {
        token: _LETTER_OFFSET + index
        for index, token in enumerate(tokens)
    }
    for order, tokens in _ALPHABET_TOKENS.items()
}
_UNKNOWN_LETTER_RANKS = {
    order: _LETTER_OFFSET + len(tokens)
    for order, tokens in _ALPHABET_TOKENS.items()
}


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


def alphabet_for_order(sort_order):
    return _ALPHABET_TOKENS.get(sort_order, _ALPHABET_TOKENS[SORT_ORDER_STANDARD])


def token_ranks_for_order(sort_order):
    return _TOKEN_RANKS.get(sort_order, _DEFAULT_TOKEN_RANKS)


def unknown_letter_rank_for_order(sort_order):
    return _UNKNOWN_LETTER_RANKS.get(
        sort_order, _DEFAULT_UNKNOWN_LETTER_RANK)


def alphabet_sort_key(text, sort_order=SORT_ORDER_STANDARD):
    if not text:
        return [], [], []
    ranks = token_ranks_for_order(sort_order)
    unknown_rank = unknown_letter_rank_for_order(sort_order)
    rank_list = []
    case_flags = []
    accent_positions = []
    index = 0
    length = len(text)
    while index < length:
        ch = text[index]
        if ch == SEP_SORT_SENTINEL:
            index += 1
            continue
        ch_lower = ch.lower()
        if ch_lower in _SEPARATOR_RANKS:
            rank_list.append(_SEPARATOR_RANKS[ch_lower])
            case_flags.append(0)
            index += 1
            continue
        if ord(ch) in _COMBINING_ACCENT_ORDS:
            if rank_list:
                accent_positions.append(len(rank_list) - 1)
            index += 1
            continue
        if ord(ch) in _SORT_IGNORED_CHAR_ORDS:
            index += 1
            continue
        token = ch_lower
        if index + 1 < length:
            pair = text[index:index + 2].lower()
            if pair in ranks:
                token = pair
        rank_list.append(ranks.get(token, unknown_rank + ord(ch)))
        case_flags.append(0 if token == text[index:index + len(token)] else 1)
        index += len(token)
    return rank_list, case_flags, accent_positions
