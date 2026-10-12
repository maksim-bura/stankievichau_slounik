"""Single source of truth for dictionary entry-markup tag attributes.

Both the app's parsing/validation code and the markup editor's content
completion prompt import from here, so declaring a new attribute once makes it
available everywhere (read sites use the ``ATTR_*`` constants). Keep
``ATTRIBUTES`` in sync with ``markup/MARKUP_PATTERNS.md``.

This is dictionary-entry markup only (``data/dictionary/*.xml``); sources.xml
(section/gabbr/…) has its own shape and is intentionally not covered here.
"""

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
    """Return a sorted list of ``(tag, attribute)`` pairs present on known tags
    but absent from ``ATTRIBUTES`` (validation helper; never raises)."""
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
