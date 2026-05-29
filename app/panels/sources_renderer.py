import re
import html
from localization import strings


def compile_search_regex(search_text):
    parts = []
    for ch in search_text:
        if ch.isupper():
            parts.append(re.escape(ch))
        elif ch.islower():
            upper = ch.upper()
            if upper != ch:
                parts.append(f'[{re.escape(ch)}{re.escape(upper)}]')
            else:
                parts.append(re.escape(ch))
        else:
            parts.append(re.escape(ch))
    return re.compile(''.join(parts), re.UNICODE)


def build_filtered_html(all_children, collapsed_sections, arrow_marker, search_text=None, marker_anchor=None):
    pattern = compile_search_regex(search_text) if search_text else None
    parts = ['<body>']

    matching_sections = [
        child for child in all_children
        if child.tag == 'section' and (pattern is None or section_matches(child, pattern))
    ]

    section_idx = 0
    needs_br = False
    seen_section = False
    for child in all_children:
        if child.tag == 'h1':
            parts.append(_element_to_html(child))
        elif child.tag == 'br' and not seen_section:
            parts.append('<br>')
        elif child.tag == 'section':
            seen_section = True
            if section_idx < len(matching_sections) and child is matching_sections[section_idx]:
                if needs_br:
                    parts.append('<br>')
                    parts.append('<br>')
                _render_section(parts, child, pattern, collapsed_sections)
                while parts and parts[-1] == '<br>':
                    parts.pop()
                section_idx += 1
                needs_br = True

    if not matching_sections:
        parts.append(strings.sources_no_results)

    while parts and parts[-1] == '<br>':
        parts.pop()

    parts.append('</body>')
    result = '\n'.join(parts)

    if marker_anchor:
        escaped = re.escape(marker_anchor)
        result = re.sub(f'(<span id="{escaped}"[^>]*>)', f'\\1{arrow_marker}', result, count=1)

    return result


def section_matches(section, pattern):
    sec_children = list(section)
    if not sec_children or sec_children[0].tag != 'h2':
        return False
    idx = 1
    while idx < len(sec_children) and sec_children[idx].tag == 'br':
        idx += 1
    gabbr_elem = None
    if section.get('id') == '4' and idx < len(sec_children) and sec_children[idx].tag == 'gabbr':
        gabbr_elem = sec_children[idx]
        idx += 1
    content = sec_children[idx:]
    gabbr_groups = _split_into_abbr_groups(list(gabbr_elem) if gabbr_elem is not None else [])
    content_groups = _split_into_abbr_groups(content)
    return any(
        _group_matches(g, pattern)
        for g in gabbr_groups + content_groups
    )


def _render_section(parts, section, pattern, collapsed_sections):
    sec_children = list(section)
    h2_elem = sec_children[0]
    section_id = section.get('id', '')

    idx = 1
    h2_br = []
    while idx < len(sec_children) and sec_children[idx].tag == 'br':
        h2_br.append('<br>')
        idx += 1

    is_collapsed = section_id in collapsed_sections
    button = f'<a class="toggle-btn" href="toggle-section:{section_id}">{"&#9654;" if is_collapsed else "&#9660;"}</a> '

    parts.append(button)
    parts.append(_element_to_html(h2_elem))

    if is_collapsed:
        return

    gabbr_elem = None
    if section.get('id') == '4' and idx < len(sec_children) and sec_children[idx].tag == 'gabbr':
        gabbr_elem = sec_children[idx]
        idx += 1

    content = sec_children[idx:]

    gabbr_groups = _split_into_abbr_groups(list(gabbr_elem) if gabbr_elem is not None else [])
    content_groups = _split_into_abbr_groups(content)

    parts.extend(h2_br)

    force_all = pattern is None
    for g in gabbr_groups:
        _render_group(parts, g, pattern, force=True)

    for g in content_groups:
        _render_group(parts, g, pattern, force=force_all)


def _split_into_abbr_groups(elements):
    groups = []
    current = []
    current_has_abbr = False
    for elem in elements:
        if elem.tag == 'br':
            if current:
                groups.append({'items': current, 'trailing_brs': 1, 'has_abbr': current_has_abbr})
                current = []
                current_has_abbr = False
            elif groups:
                groups[-1]['trailing_brs'] += 1
        else:
            current.append(elem)
            if _has_abbr(elem):
                current_has_abbr = True
    if current:
        groups.append({'items': current, 'trailing_brs': 0, 'has_abbr': current_has_abbr})
    return groups


def _group_matches(group, pattern):
    if not group['has_abbr']:
        return False
    text = ''.join(
        ''.join(elem.itertext()) + (elem.tail or '')
        for elem in group['items']
    )
    return bool(pattern.search(text))


def _render_group(parts, group, pattern, force=False):
    if not group['has_abbr']:
        if force and group['items']:
            parts.append(_render_elements(group['items'], pattern))
            for _ in range(group.get('trailing_brs', 0)):
                parts.append('<br>')
        return

    if not force and not _group_matches(group, pattern):
        return

    parts.append(_render_elements(group['items'], pattern))
    for _ in range(group.get('trailing_brs', 0)):
        parts.append('<br>')


def _has_abbr(elem):
    if elem.tag == 'abbr':
        return True
    for child in elem:
        if _has_abbr(child):
            return True
    return False


def _element_to_html(elem, pattern=None):
    tag = elem.tag
    inner_parts = []

    if elem.text:
        text = _highlight_text(html.escape(elem.text), pattern)
        inner_parts.append(text)

    for child in elem:
        inner_parts.append(_element_to_html(child, pattern))
        if child.tail:
            tail = _highlight_text(html.escape(child.tail), pattern)
            inner_parts.append(tail)

    inner_html = ''.join(inner_parts)

    if tag == 'abbr':
        anchor = (elem.text or '').rstrip(':').rstrip('.')
        return f'<span id="{anchor}" class="abbr">{inner_html}</span>'
    elif tag == 'i':
        return f'<span class="i">{inner_html}</span>'
    elif tag == 'b':
        return f'<span class="b">{inner_html}</span>'
    elif tag == 'br':
        return '<br>'
    elif tag == 'h1':
        return f'<span class="h1">{inner_html}</span>'
    elif tag == 'h2':
        return f'<span class="h2">{inner_html}</span>'
    else:
        return inner_html


def _render_elements(elements, pattern=None):
    parts = []
    for elem in elements:
        parts.append(_element_to_html(elem, pattern))
        if elem.tail:
            tail = _highlight_text(html.escape(elem.tail), pattern)
            parts.append(tail)
    return ''.join(parts)


def _highlight_text(text, pattern):
    if pattern is None or not text:
        return text
    result = []
    pos = 0
    for match in pattern.finditer(text):
        result.append(text[pos:match.start()])
        result.append(f'<span class="search-highlight">{text[match.start():match.end()]}</span>')
        pos = match.end()
    result.append(text[pos:])
    return ''.join(result)
