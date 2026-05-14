import xml.etree.ElementTree as ElementTree
import os
from .link_handler import LinkHandler
from .source_mapper import source_mapper
from .accent_utils import remove_accents

target_subheadword = None
target_senses = None
target_headword = None


def set_target_subheadword(headword):
    global target_subheadword, target_senses, target_headword
    target_subheadword = headword
    target_senses = None
    target_headword = None


def set_target_senses(sense_parts, headword=None):
    global target_senses, target_subheadword, target_headword
    target_senses = sense_parts
    target_headword = remove_accents(headword) if headword else None
    target_subheadword = None


def clear_target():
    global target_subheadword, target_senses, target_headword
    target_subheadword = None
    target_senses = None
    target_headword = None


def format_entry(xml_string, is_sources=False):
    global target_subheadword, target_senses, target_headword

    try:
        root = ElementTree.fromstring(xml_string)
        content = process_element(root, target_subheadword, target_senses, is_sources, None)

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
    except Exception as error:
        print(f"Error formatting XML: {error}")
        return xml_string


def sense_matches_headword(sense_element, target_headword):
    if not target_headword:
        return True
    hw_attr = sense_element.get('hw')
    if hw_attr:
        hw_variants = [remove_accents(v.strip()) for v in hw_attr.split('|')]
        return target_headword in hw_variants
    return True


def process_element(element, mark_word=None, mark_senses=None, is_sources=False, current_headword=None):
    parts = []

    if element.text:
        parts.append(element.text)

    for child in element:
        new_headword = current_headword
        if child.tag == 'hw' and child.text:
            new_headword = remove_accents(child.text)

        is_target_sense = False
        if mark_senses and child.tag == 'sense':
            sense_attribute = child.get('n')
            if sense_attribute:
                if sense_attribute.isdigit():
                    if int(sense_attribute) in mark_senses and sense_matches_headword(child, target_headword):
                        is_target_sense = True
                else:
                    if sense_attribute in mark_senses and sense_matches_headword(child, target_headword):
                        is_target_sense = True

        is_target_headword = (mark_word and
                              child.tag == 'hw' and
                              remove_accents(child.text) == remove_accents(mark_word))

        if child.tag == 'br':
            parts.append('<br>')
            if child.tail:
                parts.append(child.tail)
            continue

        style = get_style_for_tag(child.tag)

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
                parts.append(f'<span style="{get_style_for_tag("see")}">{link_html}</span>')
        else:
            inner_parts = []

            if is_target_headword:
                inner_parts.append('<span style="font-weight: normal; margin-right: 4px;">➡️</span>')

            if len(child) > 0:
                inner_parts.append(process_element(child, mark_word, mark_senses, is_sources, new_headword))
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


def get_style_for_tag(tag):
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