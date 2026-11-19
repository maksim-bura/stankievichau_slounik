TEXT = 'text'
BOOL = 'bool'

ATTR_ID = 'id'
ATTR_HW = 'hw'
ATTR_ENTRY = 'entry'
ATTR_EXCL = 'excl'
ATTR_KEEP_ACC = 'keep-acc'
ATTR_N = 'n'
ATTR_LANG = 'lang'
ATTR_CODE = 'code'
ATTR_SYN = 'syn'

ATTRIBUTES = {
    'entry': [(ATTR_ID, TEXT)],
    'hw':    [(ATTR_ID, TEXT), (ATTR_EXCL, BOOL), (ATTR_KEEP_ACC, BOOL)],
    'g':     [(ATTR_HW, TEXT)],
    'see':   [(ATTR_ENTRY, TEXT), (ATTR_HW, TEXT), (ATTR_SYN, BOOL)],
    'sense': [(ATTR_N, TEXT)],
    'ex':    [(ATTR_LANG, TEXT)],
    'i':     [(ATTR_LANG, TEXT), (ATTR_EXCL, BOOL)],
    'p':     [(ATTR_LANG, TEXT)],
    'lang':  [(ATTR_CODE, TEXT)],
}
