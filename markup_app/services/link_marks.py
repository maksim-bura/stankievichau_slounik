import html
import re

from markup_app.localization import strings
from markup_app.services.broken_links import (
    OUTCOME_RESOLVED, normalize_headword, strip_tags,
)


def format_link_tooltip(deps, title):
    lines = [html.escape(title)]
    for dep in deps:
        hw_label = ', '.join(dep['hws'])
        lines.append(
            f'&bull; <b>{html.escape(hw_label)}</b>: {html.escape(dep["raw"])}'
        )
    return '<br>'.join(lines)


def build_link_marks(broken_links, text, entry_id):
    target_norms = set()
    target_ids = set()
    entry_targeted = False
    deps = []
    for occ in broken_links.see_occurrences():
        if occ['outcome'] != OUTCOME_RESOLVED:
            continue
        row = occ['row']
        if row is None or row[0] != entry_id:
            continue
        entry_targeted = True
        norm = normalize_headword(row[1])
        hw_id_value = row[3] if len(row) > 3 and row[3] else None
        target_norms.add(norm)
        if hw_id_value:
            target_ids.add(hw_id_value)
        deps.append({
            'norm': norm,
            'id': hw_id_value,
            'hws': broken_links.owning_hw_texts(occ['block'], occ['start']),
            'raw': occ['block'][occ['start']:occ['end']],
        })
    for match in re.finditer(r'<g\b([^>]*)>', text):
        attr = re.search(r'\bhw\s*=\s*"([^"]*)"', match.group(1))
        if attr and attr.group(1):
            target_norms.add(normalize_headword(attr.group(1)))
            target_ids.add(attr.group(1))
    hw_offsets = []
    tooltips = {}
    for match in re.finditer(r'<hw\b([^>]*)>(.*?)</hw>', text, re.DOTALL):
        hw_id = re.search(r'\bid\s*=\s*"([^"]*)"', match.group(1))
        inner = normalize_headword(strip_tags(match.group(2)).strip())
        if inner in target_norms or (hw_id and hw_id.group(1) in target_ids):
            hw_offsets.append(match.start())
            hw_deps = [
                dep for dep in deps
                if dep['norm'] == inner
                or (d_id := dep['id']) and hw_id and d_id == hw_id.group(1)
            ]
            if hw_deps:
                tooltips[match.start()] = format_link_tooltip(
                    hw_deps, strings.editor.link_dependencies.headword.tooltip
                )
    if not entry_targeted and not hw_offsets:
        return [], {}
    offsets = list(hw_offsets)
    entry_tooltip = format_link_tooltip(
        deps, strings.editor.link_dependencies.entry.tooltip
    ) if deps else None
    for match in re.finditer(r'<entry\b[^>]*>', text):
        offsets.append(match.start())
        if entry_tooltip is not None:
            tooltips[match.start()] = entry_tooltip
    return offsets, tooltips
