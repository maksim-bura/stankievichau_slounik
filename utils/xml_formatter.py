import xml.etree.ElementTree as ElementTree
from .link_handler import LinkHandler
from .source_mapper import source_mapper
from .accent_utils import remove_accents


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


def format_entry(xml_string, is_sources=False):
    global _format_context

    root = ElementTree.fromstring(xml_string)
    context = _format_context
    content = _process_element(root, context, is_sources, None)

    html = f"""<body style="
            font-family: 'Cambria', 'Times New Roman', Times, serif;
            line-height: 1.4;
            margin: 15px;
            text-align: justify;
        ">
        {content}
        </body>"""

    if not is_sources:
        clear_target()
    return html


def _sense_matches_headword(sense_element, target_headword):
    if not target_headword:
        return True
    hw_attr = sense_element.get('hw')
    if hw_attr:
        hw_variants = [remove_accents(v.strip()) for v in hw_attr.split('|')]
        return target_headword in hw_variants
    return True


def _process_element(element, context, is_sources=False, current_headword=None):
    parts = []

    if element.text:
        parts.append(element.text)

    for child in element:
        new_headword = current_headword
        if child.tag == 'hw' and child.text:
            new_headword = remove_accents(child.text)

        is_target_sense = False
        if context and context.senses and child.tag == 'sense':
            sense_attribute = child.get('n')
            if sense_attribute:
                if sense_attribute.isdigit():
                    if int(sense_attribute) in context.senses and _sense_matches_headword(child, context.headword):
                        is_target_sense = True
                else:
                    if sense_attribute in context.senses and _sense_matches_headword(child, context.headword):
                        is_target_sense = True

        is_target_headword = (context and context.subheadword and
                              child.tag == 'hw' and
                              remove_accents(child.text) == remove_accents(context.subheadword))

        if child.tag == 'br':
            parts.append('<br>')
            if child.tail:
                parts.append(child.tail)
            continue

        style = _get_style_for_tag(child.tag)

        if LinkHandler.is_link_tag(child.tag):
            if child.tag == 'src':
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

                    if not abbreviations:
                        parts.append(inner_html)
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
                        parts.append(''.join(result_parts))
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
                            parts.append(''.join(result_parts))
                        else:
                            parts.append(inner_html)
                else:
                    parts.append('')
            else:
                hw_attr = child.get('hw')
                link_attr = child.get('link')
                link_text = child.text
                stripped_text = link_text.strip('"\'„“”') if link_text else None
                if hw_attr:
                    hw_attr = hw_attr.strip('"\'„“”')
                if link_attr:
                    link_target = link_attr
                elif hw_attr:
                    link_target = hw_attr
                else:
                    link_target = stripped_text
                link_html = LinkHandler.create_link(child.tag, link_target, display_html=link_text, hw_attr=hw_attr)
                parts.append(f'<span style="{_get_style_for_tag("see")}">{link_html}</span>')
        else:
            inner_parts = []

            if is_target_headword:
                inner_parts.append('<span style="font-weight: normal; margin-right: 4px;">➡️</span>')

            if len(child) > 0:
                inner_parts.append(_process_element(child, context, is_sources, new_headword))
            else:
                if child.text:
                    inner_parts.append(child.text)

            inner_html = ''.join(inner_parts)

            if is_target_sense:
                parts.append('<span style="margin-right: 4px;">➡️</span>')
                sense_id = f"sense_{sense_attribute}"
                parts.append(f'<span id="{sense_id}" style="{style}">{inner_html}</span>')
            elif is_sources and child.tag == 'abbr' and child.text:
                anchor_id = child.text.rstrip(':').rstrip('.')
                parts.append(f'<span id="{anchor_id}" style="{style}">{inner_html}</span>')
            elif not is_sources and child.tag == 'hw' and child.text:
                anchor_id = remove_accents(child.text)
                link_attr = child.get('link')
                comma = ''
                if child.tail and child.tail.startswith(','):
                    comma = child.tail[0]
                    child.tail = child.tail[1:]

                if link_attr:
                    parts.append(f'<span id="{link_attr}" style="{style}">{inner_html}{comma}</span>')
                else:
                    parts.append(f'<span id="{anchor_id}" style="{style}">{inner_html}{comma}</span>')
            elif style:
                parts.append(f'<span style="{style}">{inner_html}</span>')
            else:
                parts.append(inner_html)

        if child.tail:
            if child.tag == 'g' and child.tail.startswith(','):
                comma = child.tail[0]
                remaining = child.tail[1:]
                parts.append(f'<span style="font-style: italic;">{comma}</span>{remaining}')
            else:
                parts.append(child.tail)

    return ''.join(parts)


def _get_style_for_tag(tag):
    styles = {
        'hw': 'font-weight: bold;',
        'g': 'font-style: italic;',
        'ex': 'font-style: italic;',
        'i': 'font-style: italic;',
        'b': 'font-weight: bold;',
        'abbr': 'font-weight: bold;',
        'see': 'font-style: italic;',
        'p': 'font-style: normal; font-weight: normal;',
        'h1': 'font-weight: bold; font-size: 18pt; margin-bottom: 8px; display: block;',
        'h2': 'font-weight: bold; font-size: 16pt; margin-bottom: 8px; display: block;',
        'span': '',
    }
    return styles.get(tag, '')