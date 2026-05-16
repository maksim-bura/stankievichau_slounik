import re
from utils.accent_utils import remove_accents


class LinkHandler:
    LINK_TAGS = {
        'see': {'css_class': 'link word-link', 'action': 'word'},
        'src': {'css_class': 'source-link', 'action': 'source'},
    }

    @classmethod
    def create_link(cls, tag_name, link_target, display_html=None, hw_attr=None):
        if display_html is None:
            display_html = link_target

        tag_info = cls.LINK_TAGS.get(tag_name)
        if tag_info:
            if tag_name == 'src':
                from .source_mapper import source_mapper
                link_target = source_mapper.get_abbreviation(link_target)
            target = hw_attr if hw_attr else link_target
            return f'<a href="{tag_info["action"]}:{target}" class="{tag_info["css_class"]}">{display_html}</a>'
        return display_html

    @classmethod
    def is_link_tag(cls, tag_name):
        return tag_name in cls.LINK_TAGS

    @classmethod
    def parse_link_text(cls, link_text):
        normalized = remove_accents(link_text)
        match = re.match(r'^(.+?)\s+([\d\s,а-яА-Я]+)$', normalized)
        if match:
            word = match.group(1).strip()
            numbers_str = match.group(2).strip()
            sense_parts = []
            for part in re.split(r'[,\s]+', numbers_str):
                if part.isdigit():
                    sense_parts.append(int(part))
                elif part.isalpha() and len(part) == 1:
                    sense_parts.append(part)
                else:
                    for char in part:
                        if char.isalpha() and len(char) == 1:
                            sense_parts.append(char)
            return word, sense_parts
        return normalized, []

    @classmethod
    def process_url(cls, url_string):
        if url_string.startswith("word:"):
            target = url_string[5:]
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
        elif url_string.startswith("source:"):
            target = url_string[7:]
            return ('source', target, None, None)
        return (None, None, None, None)
