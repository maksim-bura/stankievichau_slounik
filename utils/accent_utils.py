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
