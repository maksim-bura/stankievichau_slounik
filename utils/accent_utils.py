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


def get_text_excluding_src(element, extra_exclude=None, skip_attrs=None):
    parts = []
    if element.text:
        parts.append(element.text)
    exclude = {'src', 'st'}
    if extra_exclude:
        exclude.update(extra_exclude)
    for child in element:
        skip = child.tag in exclude
        if not skip and skip_attrs:
            for attr_name, attr_val in skip_attrs.items():
                if attr_val is None:
                    if attr_name in child.attrib:
                        skip = True
                        break
                elif child.get(attr_name) == attr_val:
                    skip = True
                    break
        if not skip:
            if child.text:
                parts.append(child.text)
        if child.tail:
            parts.append(child.tail)
    return ''.join(parts)
