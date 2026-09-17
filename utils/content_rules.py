from utils.text_utils import normalize_jo, remove_accents


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


def content_text(element, tag):
    if tag == 't':
        return get_text_excluding_src(element, extra_exclude={'see'}, skip_attrs={'lang': 'vl', 'excl': None})
    if tag == 'ex':
        return get_text_excluding_src(element, extra_exclude={'t'})
    return get_text_excluding_src(element)


def d_hw_variants(d_element):
    variants = []
    for child in d_element:
        if child.tag == 'hw':
            text = ''.join(child.itertext()).strip()
            if text:
                variants.append(text)
    return variants


def index_text(text, tag):
    clean = remove_accents(text.lower())
    return normalize_jo(clean) if tag == 't' else clean