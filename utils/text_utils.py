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


def alphabet_sort_key(text):
    """Sort key ordering Cyrillic headwords by Belarusian alphabet order,
    placing ґ after г and before д. Non-alphabet characters fall back to a
    high base plus their Unicode ordinal so they keep a stable relative order
    after all alphabet letters."""
    if not text:
        return []
    lowered = text.lower()
    ranks = {ch: i for i, ch in enumerate(_BY_ALPHABET)}
    return [ranks.get(ch, len(_BY_ALPHABET) + ord(ch)) for ch in lowered]