TEXT = 'text'
BOOL = 'bool'

ATTR_ID = 'id'
ATTR_HW = 'hw'
ATTR_ENTRY = 'entry'
ATTR_EXCL = 'excl'
ATTR_N = 'n'
ATTR_LANG = 'lang'
ATTR_CODE = 'code'
ATTR_SYN = 'syn'

ATTRIBUTES = {
    'entry': [(ATTR_ID, TEXT)],
    'hw':    [(ATTR_ID, TEXT), (ATTR_EXCL, BOOL)],
    'g':     [(ATTR_HW, TEXT)],
    'see':   [(ATTR_ENTRY, TEXT), (ATTR_HW, TEXT), (ATTR_SYN, BOOL)],
    'sense': [(ATTR_N, TEXT)],
    'i':     [(ATTR_LANG, TEXT), (ATTR_EXCL, BOOL)],
    'lang':  [(ATTR_CODE, TEXT)],
}

_BOOL_ATTRS = {
    tag: frozenset(name for name, kind in spec if kind == BOOL)
    for tag, spec in ATTRIBUTES.items()
}


def attribute_names(tag):
    return [name for name, _ in ATTRIBUTES.get(tag, ())]


def is_boolean(tag, name):
    return name in _BOOL_ATTRS.get(tag, ())


def unknown_attributes(root):
    found = set()
    for element in root.iter():
        spec = ATTRIBUTES.get(element.tag)
        if not spec:
            continue
        valid = {name for name, _ in spec}
        for attribute in element.attrib:
            if attribute not in valid:
                found.add((element.tag, attribute))
    return sorted(found)
