import re

from dictionary_app.utils.remove_accents import remove_accents

_KEEP_ACC_ATTR_RE = re.compile(r'(?:^|\s)keep-acc(?![\w-])')

QUOTE_CHARS = '"\''


def strip_quotes(text):
    return text.strip(QUOTE_CHARS) if text else text


def resolve_headword(text, keep_acc):
    if keep_acc:
        return text
    return remove_accents(text)


def has_keep_acc(attrs_text):
    return bool(attrs_text) and _KEEP_ACC_ATTR_RE.search(attrs_text) is not None


def normalize_jo_to_je(text):
    if not text:
        return text
    return text.replace('ё', 'е').replace('Ё', 'Е')
