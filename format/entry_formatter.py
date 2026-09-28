import re
import xml.etree.ElementTree as ElementTree
from collections import OrderedDict
from .link_handler import LinkHandler
from .source_mapper import source_mapper
from utils.text_utils import remove_accents
from utils.content_rules import d_hw_variants
from utils.constants import ARROW_MARKER, SENSE_ANCHOR_PREFIX

_ITALIC_TEXT_TAGS = {'g', 'ex', 'i', 'st', 'see'}

_PLAIN_PAREN_TAGS = _ITALIC_TEXT_TAGS | {'hw'}

_PAREN_WRAP_RE = re.compile(r'[()]')

_BOLD_BRACKET_TAGS = {'hw', 'src', 'st'}

_TAG_CLASSES = {
    'hw': 'hw',
    'g': 'g',
    'ex': 'ex',
    'i': 'i',
    'b': 'b',
    'n': 'n',
    'abbr': 'abbr',
    'see': 'see',
    'p': 'p',
    't': 't',
}


def _get_class_for_tag(tag):
    return _TAG_CLASSES.get(tag, '')


def _find_bracket_bold(element):
    children = list(element)
    runs = []
    if element.text:
        runs.append((-1, element.text))
    for idx, child in enumerate(children):
        if child.tail:
            runs.append((idx, child.tail))

    text_positions = []
    tail_positions = {}
    i = 0
    while i < len(runs):
        open_child, open_text = runs[i]
        open_pos = open_text.find('[')
        if open_pos == -1:
            i += 1
            continue

        j = i
        close_run = -1
        close_pos = -1
        while j < len(runs):
            close_child, close_text = runs[j]
            base = open_pos + 1 if j == i else 0
            pos = close_text.find(']', base)
            if pos != -1:
                close_run = j
                close_pos = pos
                break
            j += 1
        if close_run == -1:
            i += 1
            continue

        start_child = 0 if open_child == -1 else open_child + 1
        end_child = runs[close_run][0]
        if end_child < start_child:
            i = close_run + 1
            continue

        inner_tags = [c.tag for c in children[start_child:end_child + 1]]
        if (inner_tags and 'hw' in inner_tags
                and all(tag in _BOLD_BRACKET_TAGS for tag in inner_tags)):
            if open_child == -1:
                text_positions.append(open_pos)
            else:
                tail_positions.setdefault(open_child, []).append(open_pos)
            if runs[close_run][0] == -1:
                text_positions.append(close_pos)
            else:
                tail_positions.setdefault(runs[close_run][0], []).append(close_pos)
        i = close_run + 1

    return text_positions, tail_positions


def _bold_brackets(text, positions):
    if not positions:
        return text
    parts = []
    last = 0
    for pos in sorted(positions):
        parts.append(text[last:pos])
        parts.append(f'<b>{text[pos]}</b>')
        last = pos + 1
    parts.append(text[last:])
    return ''.join(parts)


def _plain_parens(text):
    if not text or ('(' not in text and ')' not in text):
        return text
    parts = []
    pos = 0
    for m in re.finditer(r'<[^>]+>', text):
        parts.append(_PAREN_WRAP_RE.sub(lambda x: f'<span class="p">{x.group(0)}</span>', text[pos:m.start()]))
        parts.append(m.group(0))
        pos = m.end()
    parts.append(_PAREN_WRAP_RE.sub(lambda x: f'<span class="p">{x.group(0)}</span>', text[pos:]))
    return ''.join(parts)


class FormatContext:
    def __init__(self, subheadword=None, senses=None, headword=None):
        self.subheadword = subheadword
        self.senses = senses
        self.headword = headword


_format_context = None


def set_target_subheadword(headword):
    global _format_context
    _format_context = FormatContext(subheadword=headword)


def set_target_senses(sense_parts, headword=None):
    global _format_context
    _format_context = FormatContext(senses=sense_parts, headword=remove_accents(headword) if headword else None)


def clear_target():
    global _format_context
    _format_context = None


_FORMAT_CACHE_MAX_SIZE = 512
_format_cache = OrderedDict()


def format_entry(xml_string, is_sources=False):
    global _format_context
    if not is_sources and _format_context is None:
        cached = _format_cache.get(xml_string)
        if cached is not None:
            _format_cache.move_to_end(xml_string)
            return cached

    root = ElementTree.fromstring(xml_string)
    context = _format_context
    content = process_element(root, context, is_sources)

    html = f"<body>{content}</body>"

    if not is_sources and _format_context is None:
        _format_cache[xml_string] = html
        while len(_format_cache) > _FORMAT_CACHE_MAX_SIZE:
            _format_cache.popitem(last=False)
    if not is_sources:
        clear_target()
    return html


def _sense_matches_headword(sense_element, target_headword, variants=None):
    if not target_headword:
        return True
    if variants:
        return target_headword in variants
    hw_attr = sense_element.get('hw')
    if hw_attr:
        hw_variants = [remove_accents(v.strip()) for v in hw_attr.split('|')]
        return target_headword in hw_variants
    return True


def _d_variants(element):
    return [remove_accents(text) for text in d_hw_variants(element)]


def process_element(element, context, is_sources=False, current_variants=None):
    parts = []
    children = list(element)
    text_positions, tail_positions = _find_bracket_bold(element)
    if text_positions and element.text:
        element.text = _bold_brackets(element.text, text_positions)
    for tail_idx, tail_pos_list in tail_positions.items():
        child_tail = children[tail_idx].tail
        if child_tail:
            children[tail_idx].tail = _bold_brackets(child_tail, tail_pos_list)

    if element.text:
        parts.append(_plain_parens(element.text) if element.tag in _PLAIN_PAREN_TAGS else element.text)

    for child in children:
        new_variants = current_variants
        if child.tag == 'd':
            d_variants = _d_variants(child)
            if d_variants:
                new_variants = d_variants

        is_target_sense = False
        if context and context.senses and child.tag == 'sense':
            sense_attribute = child.get('n')
            if sense_attribute:
                normalized = int(sense_attribute) if sense_attribute.isdigit() else sense_attribute
                if normalized in context.senses and _sense_matches_headword(child, context.headword, current_variants):
                    is_target_sense = True

        is_target_headword = (context and context.subheadword and
                              child.tag == 'hw' and
                              remove_accents(''.join(child.itertext()).strip()) == remove_accents(context.subheadword))

        if child.tag == 'br':
            parts.append('<br>')
            if child.tail:
                parts.append(child.tail)
            continue

        tag_class = _get_class_for_tag(child.tag)

        if LinkHandler.is_link_tag(child.tag):
            if child.tag in ('src', 'st'):
                inner_html_parts = []
                for inner_child in child:
                    if inner_child.tag == 'b':
                        inner_html_parts.append(f'<b>{inner_child.text}</b>')
                    elif inner_child.tag == 'i':
                        inner_html_parts.append(f'<i>{inner_child.text}</i>')
                    else:
                        if inner_child.text:
                            inner_html_parts.append(inner_child.text)
                    if inner_child.tail:
                        inner_html_parts.append(inner_child.tail)
                if child.text:
                    inner_html_parts.insert(0, child.text)
                source_text = ''.join(child.itertext()).strip()
                inner_html = ''.join(inner_html_parts).strip()

                if source_text:
                    abbreviations = source_mapper.extract_abbreviations(source_text)

                    def _wrap_src(content):
                        if child.tag == 'src':
                            return f'<span class="src">{content}</span>'
                        if child.tag == 'st':
                            return f'<span class="st">{_plain_parens(content)}</span>'
                        return content

                    if not abbreviations:
                        parts.append(_wrap_src(inner_html))
                    elif len(abbreviations) > 1:
                        abbrevs_with_positions = []
                        for abbr, variant in abbreviations:
                            pos = source_text.find(variant)
                            if pos != -1:
                                abbrevs_with_positions.append((pos, abbr, variant))
                        abbrevs_with_positions.sort(key=lambda x: x[0])

                        result_parts = []
                        current_pos = 0
                        for pos, abbr, variant in abbrevs_with_positions:
                            if pos > current_pos:
                                result_parts.append(inner_html[current_pos:pos])
                            result_parts.append(LinkHandler.create_link(child.tag, abbr, inner_html[pos:pos + len(variant)]))
                            current_pos = pos + len(variant)
                        if current_pos < len(inner_html):
                            result_parts.append(inner_html[current_pos:])
                        parts.append(_wrap_src(''.join(result_parts)))
                    else:
                        abbr, variant = abbreviations[0]
                        pos = source_text.find(variant)
                        if pos != -1:
                            html_pos = 0
                            text_pos = 0
                            i = 0
                            in_tag = False
                            while i < len(inner_html) and text_pos < pos:
                                if inner_html[i] == '<':
                                    in_tag = True
                                elif inner_html[i] == '>':
                                    in_tag = False
                                elif not in_tag:
                                    text_pos += 1
                                i += 1
                            html_pos = i

                            variant_len = len(variant)
                            i = html_pos
                            text_pos = 0
                            in_tag = False
                            while i < len(inner_html) and text_pos < variant_len:
                                if inner_html[i] == '<':
                                    in_tag = True
                                elif inner_html[i] == '>':
                                    in_tag = False
                                elif not in_tag:
                                    text_pos += 1
                                i += 1
                            variant_html_end = i

                            result_parts = []
                            if html_pos > 0:
                                result_parts.append(inner_html[:html_pos])
                            result_parts.append(LinkHandler.create_link(child.tag, abbr, inner_html[html_pos:variant_html_end]))
                            if variant_html_end < len(inner_html):
                                result_parts.append(inner_html[variant_html_end:])
                            parts.append(_wrap_src(''.join(result_parts)))
                        else:
                            parts.append(_wrap_src(inner_html))
                else:
                    parts.append('')
            else:
                hw_attr = child.get('hw')
                link_attr = child.get('link')
                display_text = ''.join(child.itertext()).strip() or child.text
                see_text = display_text.strip('"\'„“”') or display_text
                if hw_attr:
                    hw_attr = hw_attr.strip('"\'„“”')
                if link_attr:
                    link_target = link_attr
                elif hw_attr:
                    link_target = hw_attr
                else:
                    link_target = see_text
                    if any(grand == 'n' for grand in child) and re.match(r'^[,\s]*\d', child.tail or ''):
                        link_target += (child.tail or '')
                link_html = LinkHandler.create_link(child.tag, link_target, display_html=_plain_parens(display_text) or display_text, hw_attr=hw_attr)
                parts.append(f'<span class="see">{link_html}</span>')
        else:
            inner_parts = []

            if is_target_headword:
                inner_parts.append(f'<span class="headword-arrow">{ARROW_MARKER}</span>')

            if len(child) > 0:
                inner_parts.append(process_element(child, context, is_sources, new_variants))
            else:
                if child.text:
                    inner_parts.append(_plain_parens(child.text) if child.tag in _PLAIN_PAREN_TAGS else child.text)

            inner_html = ''.join(inner_parts)

            if is_target_sense:
                sense_id = f"{SENSE_ANCHOR_PREFIX}{sense_attribute}"
                parts.append(f'<span class="sense-arrow">{ARROW_MARKER}</span>')
                parts.append(f'<span id="{sense_id}" class="{tag_class}">{inner_html}</span>' if tag_class else f'<span id="{sense_id}">{inner_html}</span>')
            elif is_sources and child.tag == 'abbr' and child.text:
                anchor_id = child.text.rstrip(':').rstrip('.')
                parts.append(f'<span id="{anchor_id}" class="{tag_class}">{inner_html}</span>' if tag_class else f'<span id="{anchor_id}">{inner_html}</span>')
            elif not is_sources and child.tag == 'hw':
                hw_text = ''.join(child.itertext()).strip() or child.text
                anchor_id = remove_accents(hw_text)
                link_attr = child.get('link')
                sep = ''
                if child.tail and child.tail.startswith((',', ':', ';')):
                    sep = child.tail[0]
                    child.tail = child.tail[1:]

                if link_attr:
                    parts.append(f'<span id="{link_attr}" class="{tag_class}">{inner_html}{sep}</span>' if tag_class else f'<span id="{link_attr}">{inner_html}{sep}</span>')
                else:
                    parts.append(f'<span id="{anchor_id}" class="{tag_class}">{inner_html}{sep}</span>' if tag_class else f'<span id="{anchor_id}">{inner_html}{sep}</span>')
            elif tag_class:
                parts.append(f'<span class="{tag_class}">{inner_html}</span>')
            else:
                parts.append(inner_html)

        if child.tail:
            if child.tag == 'g' and child.tail.startswith(','):
                comma = child.tail[0]
                remaining = child.tail[1:]
                if element.tag in _ITALIC_TEXT_TAGS:
                    remaining = _plain_parens(remaining)
                parts.append(f'<span class="g">{comma}</span>{remaining}')
            else:
                parts.append(_plain_parens(child.tail) if element.tag in _PLAIN_PAREN_TAGS else child.tail)

    return ''.join(parts)
