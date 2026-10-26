from dictionary_app.utils.normalize_headword import normalize_jo_to_je
from dictionary_app.utils.remove_accents import remove_accents
from dictionary_app.utils.xml_schema import ATTR_CODE, ATTR_LANG, ATTR_EXCL


def is_excluded_child(child, tag):
    if child.tag in ('src', 'st'):
        return True
    if tag == 't':
        if child.tag in ('see', 'g', 'ex'):
            return True
        if child.tag == 'lang':
            return child.get(ATTR_CODE) in ('vl', 'la') or ATTR_EXCL in child.attrib
        return child.get(ATTR_LANG) == 'vl' or ATTR_EXCL in child.attrib
    if tag == 'ex':
        if child.tag == 't':
            return True
        if child.tag == 'lang':
            return child.get(ATTR_CODE) == 'ru'
        return child.get(ATTR_LANG) == 'ru'
    return False


def content_text(element, tag):
    parts = []
    if element.text:
        parts.append(element.text)
    for child in element:
        if not is_excluded_child(child, tag) and child.text:
            parts.append(child.text)
        if child.tail:
            parts.append(child.tail)
    return ''.join(parts)


def hw_text_excluding_n(element):
    parts = []
    if element.text:
        parts.append(element.text)
    for child in element:
        if child.tag == 'n':
            if child.tail:
                parts.append(child.tail)
            continue
        parts.append(hw_text_excluding_n(child))
        if child.tail:
            parts.append(child.tail)
    return ''.join(parts)


def d_hw_variants(d_element, exclude_n=False):
    variants = []
    for child in d_element:
        if child.tag == 'hw' and child.get(ATTR_EXCL) is None:
            text = (hw_text_excluding_n(child) if exclude_n else ''.join(child.itertext())).strip()
            if text:
                variants.append(text)
    return variants


def index_text(text, tag):
    clean = remove_accents(text.lower())
    return normalize_jo_to_je(clean) if tag == 't' else clean