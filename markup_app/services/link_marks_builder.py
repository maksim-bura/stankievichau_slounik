import html
import re

from dictionary_app.utils.normalize_headword import has_keep_acc, resolve_headword

from markup_app.localization import strings
from markup_app.services.broken_link_analyzer import OUTCOME_RESOLVED, attr_matches, normalize_headword, split_sense_tail, strip_tags


def format_link_tooltip(deps, title):
    lines = [html.escape(title)]
    for dep in deps:
        hw_label = ', '.join(dep['hws'])
        lines.append(
            f'&bull; <b>{html.escape(hw_label)}</b>: {html.escape(dep["raw"])}'
        )
    return '<br>'.join(lines)


def build_link_marks(broken_links, text, entry_id):
    cur_link = None
    entry_tag = re.search(r'<entry\b([^>]*)>', text)
    if entry_tag:
        id_match = re.search(r'\bid\s*=\s*"([^"]*)"', entry_tag.group(1))
        if id_match:
            cur_link = id_match.group(1)
    cur_hws = []
    cur_hw_ids = set()
    cur_hw_norms = set()
    for hw_match in re.finditer(r'<hw\b([^>]*)>(.*?)</hw>', text, re.DOTALL):
        raw_hw = strip_tags(hw_match.group(2)).strip()
        if not raw_hw:
            continue
        cur_hws.append(raw_hw)
        cur_hw_norms.add(normalize_headword(raw_hw))
        cur_hw_norms.add(resolve_headword(
            raw_hw, has_keep_acc(hw_match.group(1))))
        hw_id_match = re.search(r'\bid\s*=\s*"([^"]*)"', hw_match.group(1))
        if hw_id_match:
            cur_hw_ids.add(hw_id_match.group(1))

    def still_targets(occ):
        ea = occ['entry_attr']
        ha = occ['hw_attr']
        if ea:
            if not ((cur_link and attr_matches(ea, cur_link))
                    or any(attr_matches(ea, h) for h in cur_hws)):
                return False
            if ha and not (ha in cur_hw_ids
                           or any(attr_matches(ha, h) for h in cur_hws)):
                return False
            return True
        if ha:
            return ha in cur_hw_ids or any(
                attr_matches(ha, h) for h in cur_hws)
        word = split_sense_tail(occ['word'])[0]
        return normalize_headword(word) in cur_hw_norms

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
        if not still_targets(occ):
            continue
        entry_targeted = True
        norm = resolve_headword(row[1], row[4] if len(row) > 4 else 0)
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
    g_hw_attrs = []
    for match in re.finditer(r'<g\b([^>]*)>', text):
        attr = re.search(r'\bhw\s*=\s*"([^"]*)"', match.group(1))
        if attr and attr.group(1):
            g_hw_attrs.append(attr.group(1))
            target_ids.add(attr.group(1))
    hw_offsets = []
    tooltips = {}
    for match in re.finditer(r'<hw\b([^>]*)>(.*?)</hw>', text, re.DOTALL):
        hw_id = re.search(r'\bid\s*=\s*"([^"]*)"', match.group(1))
        hw_text = strip_tags(match.group(2)).strip()
        inner = resolve_headword(hw_text, has_keep_acc(match.group(1)))
        if (inner in target_norms
                or any(attr_matches(attr, hw_text) for attr in g_hw_attrs)
                or (hw_id and hw_id.group(1) in target_ids)):
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
