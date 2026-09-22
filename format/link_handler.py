import re
from utils.constants import SCHEME_WORD, SCHEME_SOURCE
from utils.text_utils import remove_accents


class LinkHandler:
    LINK_TAGS = {
        'see': {'css_class': 'link word-link', 'action': 'word'},
        'src': {'css_class': 'source-link', 'action': 'source'},
        'st': {'css_class': 'source-link st-link', 'action': 'source'},
    }

    @classmethod
    def create_link(cls, tag_name, link_target, display_html=None, hw_attr=None):
        if display_html is None:
            display_html = link_target

        tag_info = cls.LINK_TAGS.get(tag_name)
        if tag_info:
            if tag_info['action'] == 'source':
                from .source_mapper import source_mapper
                link_target = source_mapper.get_abbreviation(link_target)
            target = hw_attr if hw_attr else link_target
            extra_style = ' style="font-style: normal;"' if tag_name == 'src' else ''
            return f'<a href="{tag_info["action"]}:{target}" class="{tag_info["css_class"]}"{extra_style}>{display_html}</a>'
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
            if re.fullmatch(r'[а-яА-Яa-zA-Z]', token) and not re.fullmatch(r'[ІіIi]', token):
                sense_parts.insert(0, token)
                i -= 1
                continue
            break

        homonym = ''
        if i >= 0 and re.fullmatch(r'[ІіIiVvXx]+', tokens[i]):
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
            target = url_string[len(word_prefix):]
            if '|' in target:
                parts = target.split('|')
                word = parts[0]
                hw = parts[1] if len(parts) > 1 else None
                word, sense_parts = cls.parse_link_text(word)
                return ('word', word, sense_parts, hw)
            if '#' in target:
                entry_id, anchor = target.split('#', 1)
                word, sense_parts = cls.parse_link_text(anchor)
                return ('word', word, sense_parts, entry_id)
            word, sense_parts = cls.parse_link_text(target)
            return ('word', word, sense_parts, None)
        elif url_string.startswith(source_prefix):
            target = url_string[len(source_prefix):]
            return ('source', target, None, None)
        return (None, None, None, None)
