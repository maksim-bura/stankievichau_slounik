def remove_accents(text):
    if not text:
        return text
    accent_map = {
        'а́': 'а', 'а̀': 'а',
        'е́': 'е', 'ѐ': 'е',
        'і́': 'і', 'і̀': 'і',
        'о́': 'о', 'о̀': 'о',
        'у́': 'у', 'у̀': 'у',
        'ы́': 'ы', 'ы̀': 'ы',
        'э́': 'э', 'э̀': 'э',
        'ю́': 'ю', 'ю̀': 'ю',
        'я́': 'я', 'я̀': 'я',
    }
    result = text
    for accented, base in accent_map.items():
        result = result.replace(accented, base)
    return result


def normalize_jo(text):
    """Replace ё with е for е=ё search equivalence."""
    if not text:
        return text
    return text.replace('ё', 'е').replace('Ё', 'Е')


_BY_ALPHABET = 'абвгґдеёжзійклмнопрстуўфхцчшыьэюя'


_COMBINING_ACCENT_ORDS = {0x0300, 0x0301}
_SEPARATOR_RANKS = {'-': 0, ' ': 1}
_LETTER_OFFSET = 2


def alphabet_sort_key(text):
    """Sort key ordering Cyrillic headwords by Belarusian alphabet order,
    placing ґ after г and before д.

    - Combine accents (U+0300/U+0301) are skipped so accented and
      unaccented positions compare equally (e.g. ґаґаць sorts between
      ґавыліць and ґазавы, and ґазавы before ґатунак).
    - Word breaks (space, hyphen) are strong dividers ranked BELOW all
      letters, so a multi-word entry groups immediately after its single
      headword: ґаз, ґаз сьвяціць, ґаза, ґазавая ґрана́та, ...
    - Between the two break symbols, hyphen (0) sorts before space (1).
    - Other non-alphabet characters fall back to a high base plus their
      Unicode ordinal so they keep a stable relative order after letters.
    """
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