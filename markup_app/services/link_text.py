import re

from dictionary_app.utils.remove_accents import remove_accents


_TAG_RE = re.compile(r'<[^>]+>')
_SEE_TAIL_SUFFIX_RE = re.compile(r'[,\s]*\d+(?:[,.]\s*\d+)*$')


def normalize_headword(text):
    return remove_accents(text)


def row_norm(text):
    return remove_accents(text).lower()


def strip_tags(text):
    return _TAG_RE.sub('', text)


def split_sense_tail(text):
    if not text:
        return text, []
    match = _SEE_TAIL_SUFFIX_RE.search(text)
    if match is None:
        return text, []
    word = text[:match.start()].strip() or text
    senses = [int(tok) for tok in re.findall(r'\d+', match.group(0))]
    return word, senses


def attr_matches(attr, headword):
    if not attr:
        return False
    if remove_accents(attr) != attr:
        return attr == headword
    return remove_accents(attr) == remove_accents(headword)
