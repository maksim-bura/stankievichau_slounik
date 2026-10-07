import re
from urllib.parse import unquote

from utils.constants import SCHEME_WORD, SCHEME_SOURCE
from utils.text_utils import remove_accents
from .source_mapper import source_mapper

_HOMONYM_NUMERAL_RE = re.compile(r'[ІіIiVvXxХхУу]+')
_SENSE_LETTER_RE = re.compile(r'[а-яА-Яa-zA-Z]')


class LinkHandler:
    LINK_TAGS = {
        'see': {'css_class': 'link word-link', 'action': 'word'},
        'src': {'css_class': 'source-link', 'action': 'source'},
        'st': {'css_class': 'source-link st-link', 'action': 'source'},
    }

    @classmethod
    def create_link(cls, tag_name, link_target, display_html=None):
        if display_html is None:
            display_html = link_target

        tag_info = cls.LINK_TAGS.get(tag_name)
        if tag_info:
            if tag_info['action'] == 'source':
                link_target = source_mapper.get_abbreviation(link_target)
            return f'<a href="{tag_info["action"]}:{link_target}" class="{tag_info["css_class"]}">{display_html}</a>'
        return display_html

    @classmethod
    def is_link_tag(cls, tag_name):
        return tag_name in cls.LINK_TAGS

    @classmethod
    def parse_link_text(cls, link_text):
        normalized = remove_accents(link_text)
        tokens = [t for t in re.split(r'[\s,，]+', normalized) if t]
        if not tokens:
            return normalized, []

        sense_parts = []
        i = len(tokens) - 1
        while i >= 0:
            token = tokens[i]
            if token.isdigit():
                sense_parts.insert(0, int(token))
                i -= 1
                continue
            if _SENSE_LETTER_RE.fullmatch(token) and not _HOMONYM_NUMERAL_RE.fullmatch(token):
                sense_parts.insert(0, token)
                i -= 1
                continue
            break

        homonym = ''
        if i >= 0 and _HOMONYM_NUMERAL_RE.fullmatch(tokens[i]):
            homonym = tokens[i]
            i -= 1

        word = ' '.join(tokens[:i + 1]).strip()
        if homonym:
            word = (word + ' ' if word else '') + homonym
        return word, sense_parts

    @classmethod
    def process_url(cls, url_string):
        word_prefix = SCHEME_WORD + ':'
        source_prefix = SCHEME_SOURCE + ':'
        if url_string.startswith(word_prefix):
            # QUrl percent-encodes the entry/target separator as %7C
            target = unquote(url_string[len(word_prefix):])
            if '|' in target:
                entry, _sep, target_hw = target.partition('|')
                entry, sense_parts = cls.parse_link_text(entry)
                return ('word', entry, sense_parts, target_hw or None)
            word, sense_parts = cls.parse_link_text(target)
            return ('word', word, sense_parts, None)
        elif url_string.startswith(source_prefix):
            target = url_string[len(source_prefix):]
            return ('source', target, None, None)
        return (None, None, None, None)
