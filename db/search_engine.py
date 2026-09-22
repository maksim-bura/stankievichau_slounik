import copy
import re
import sqlite3
import xml.etree.ElementTree as ElementTree
from utils.text_utils import remove_accents, normalize_jo, alphabet_sort_key
from utils.content_rules import content_text, index_text, d_hw_variants, hw_text_excluding_n
from utils.search_regex import compile_search_regex
from format.entry_formatter import process_element


_EXCLUDED_HIGHLIGHT_CLASS = 'search-excluded'

_HEADWORD_ROWS_SQL = """
    SELECT id, headword, full_entry, entry_link, source_file, sort_headword FROM dictionary
    {dictionary_where}
    UNION
    SELECT dictionary.id, sub_headwords.headword, dictionary.full_entry, dictionary.entry_link, dictionary.source_file, sub_headwords.sort_headword
    FROM sub_headwords
    JOIN dictionary ON sub_headwords.main_entry_id = dictionary.id
    {sub_headwords_where}
"""


class SearchEngine:
    def __init__(self, database_path):
        self.database_path = database_path
        self._connection = None
        self._parsed_cache = {}

    def _get_connection(self):
        if self._connection is None:
            self._connection = sqlite3.connect(self.database_path)
        return self._connection

    def get_parsed_entry(self, entry_id, xml_string=None):
        if entry_id in self._parsed_cache:
            return self._parsed_cache[entry_id]

        if xml_string is None:
            return None

        root = ElementTree.fromstring(xml_string)
        self._parsed_cache[entry_id] = root
        return root

    def get_main_headword(self, entry_id, xml_string=None):
        root = self.get_parsed_entry(entry_id, xml_string)
        element = root.find('.//hw') if root is not None else None
        if element is None:
            return ""
        return ''.join(element.itertext()).strip()

    def search(self, text, search_in_headwords=True, search_in_translations=False, search_in_examples=False):
        clean_text = remove_accents(text.strip())

        exclusive_count = sum([search_in_translations, search_in_examples])
        if exclusive_count == 1 and not search_in_headwords:
            if clean_text == "":
                return self._get_all_entries()
            if search_in_translations:
                return self._search_translations(text)
            else:
                return self._search_examples(text)

        return self._search_headwords(text)

    def _get_all_entries(self):
        return self._search_headwords("")

    def _search_headwords(self, text):
        conn = self._get_connection()
        cursor = conn.cursor()

        clean_text = remove_accents(text.strip())

        if clean_text == "":
            cursor.execute(_HEADWORD_ROWS_SQL.format(
                dictionary_where='', sub_headwords_where=''))
            unique = cursor.fetchall()
            unique.sort(key=lambda x: alphabet_sort_key(x[5] or x[1]))
            return [(r[0], r[1], r[2], r[3], r[4]) + (None,) for r in unique if r[1] != "!SOURCES"]

        pattern = compile_search_regex(clean_text, exact_words=text.endswith(' '))
        sql_pattern = self._like_pattern(clean_text.lower(), collapse_spaces=True)

        cursor.execute(_HEADWORD_ROWS_SQL.format(
            dictionary_where='WHERE normalized_headword LIKE ?',
            sub_headwords_where='WHERE sub_headwords.normalized_headword LIKE ?',
        ), (sql_pattern, sql_pattern))
        unique = cursor.fetchall()

        unique = [r for r in unique if pattern.search(remove_accents(r[5] or r[1]))]
        unique.sort(key=lambda x: alphabet_sort_key(x[5] or x[1]))
        return [(r[0], r[1], r[2], r[3], r[4]) + (None,) for r in unique]

    @staticmethod
    def _like_pattern(text, collapse_spaces=False):
        pattern = text.replace('?', '_').replace('*', '%')
        if collapse_spaces:
            pattern = pattern.replace(' ', '%')
        return '%' + pattern + '%'

    def _search_via_index(self, text, tag_type):
        clean = index_text(text.strip(), tag_type)
        pattern = compile_search_regex(clean, exact_words=text.endswith(' '))

        sql_pattern = self._like_pattern(clean)

        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT DISTINCT entry_id FROM content_index
            WHERE searchable_text LIKE ? AND tag_type = ?
        """, (sql_pattern, tag_type))
        entry_ids = [r[0] for r in cursor.fetchall()]
        if not entry_ids:
            return []

        placeholders = ','.join(['?'] * len(entry_ids))
        params = entry_ids + entry_ids

        cursor.execute(f"""
            SELECT id, headword, full_entry, entry_link, source_file FROM dictionary
            WHERE id IN ({placeholders})
            UNION
            SELECT dictionary.id, sub_headwords.headword, dictionary.full_entry, dictionary.entry_link, dictionary.source_file
            FROM sub_headwords
            JOIN dictionary ON sub_headwords.main_entry_id = dictionary.id
            WHERE dictionary.id IN ({placeholders})
        """, params)
        unique = cursor.fetchall()
        self._annotate_content_matches(unique, tag_type, pattern)
        return [r for r in unique if r[5]]

    def _search_translations(self, text):
        return self._search_via_index(text, 't')

    def _search_examples(self, text):
        return self._search_via_index(text, 'ex')

    def _annotate_content_matches(self, results, tag, pattern):
        previews_by_entry = {}
        seen_ids = set()
        deduped = []
        for result in results:
            eid = result[0]
            if eid in seen_ids:
                continue
            seen_ids.add(eid)
            deduped.append(result)
        results[:] = deduped
        for i, result in enumerate(results):
            entry_id, headword, full_entry = result[:3]
            if entry_id not in previews_by_entry:
                root = self.get_parsed_entry(entry_id, full_entry)
                previews_by_entry[entry_id] = self._find_content_matches(root, headword, tag, pattern)
            results[i] = result[:5] + (previews_by_entry[entry_id],)

    def _find_content_matches(self, root, headword, tag, pattern):
        parent_map = {c: p for p in root.iter() for c in p}
        order = list(root.iter())
        order_pos = {id(el): i for i, el in enumerate(order)}

        matched = []
        for element in root.iter(tag):
            search_text = content_text(element, tag)
            if not search_text:
                continue
            normalized_search = normalize_jo(remove_accents(search_text)) if tag == 't' else remove_accents(search_text)
            if pattern.search(normalized_search):
                matched.append(element)

        if tag == 't':
            matched_ids = {id(el) for el in matched}
            absorbed = set()
            for el in matched:
                parent = parent_map.get(el)
                if parent is None:
                    continue
                siblings = list(parent)
                try:
                    i = siblings.index(el)
                except ValueError:
                    continue
                if i >= 2:
                    prev = siblings[i - 1]
                    prev2 = siblings[i - 2]
                    if (prev.tag == 'ex' and prev.tail and '—' in prev.tail
                            and prev2.tag == 't' and id(prev2) in matched_ids):
                        absorbed.add(id(el))
            matched = [el for el in matched if id(el) not in absorbed]

            embedded_groups, embedded_by_sense = self._group_embedded_t_matches(matched, parent_map)
            if embedded_by_sense:
                consumed_senses = set()
                skipped_main_t = set()
                for group in embedded_by_sense.values():
                    main_t = group['sense'].find('t')
                    if main_t is not None:
                        skipped_main_t.add(id(main_t))
                embedded_previews = []
                prev_element = None
                for element in matched:
                    group = embedded_groups.get(id(element))
                    if group is not None:
                        if id(group['sense']) in consumed_senses:
                            continue
                        consumed_senses.add(id(group['sense']))
                        paragraph_break = self._has_br_between(prev_element, element, order, order_pos)
                        preview = self._build_embedded_t_preview(group, pattern, parent_map, root, headword)
                        preview['paragraph_break'] = paragraph_break
                        embedded_previews.append(preview)
                        prev_element = element
                        continue
                    if id(element) in skipped_main_t:
                        continue
                    paragraph_break = self._has_br_between(prev_element, element, order, order_pos)
                    preview_hw, preview_sort = self._preview_hw_fields(element, parent_map, root, headword)
                    rank = self._compute_t_match_rank(element, pattern, tag)
                    preview_html = self._build_preview_html(element, tag, pattern, parent_map)
                    embedded_previews.append({
                        'headword': preview_hw,
                        'sort_headword': preview_sort,
                        'preview_html': preview_html,
                        'paragraph_break': paragraph_break,
                        'rank': rank,
                    })
                    prev_element = element
                return embedded_previews

        previews = []
        prev_element = None
        for element in matched:
            paragraph_break = self._has_br_between(prev_element, element, order, order_pos)

            preview_hw, preview_sort = self._preview_hw_fields(element, parent_map, root, headword)

            rank = self._compute_t_match_rank(element, pattern, tag)

            preview_html = self._build_preview_html(element, tag, pattern, parent_map)
            previews.append({
                'headword': preview_hw,
                'sort_headword': preview_sort,
                'preview_html': preview_html,
                'paragraph_break': paragraph_break,
                'rank': rank,
            })
            prev_element = element
        seen_html = set()
        unique = []
        for p in previews:
            if p['preview_html'] not in seen_html:
                seen_html.add(p['preview_html'])
                unique.append(p)
        return unique

    def _has_br_between(self, prev_element, element, order, order_pos):
        if prev_element is None:
            return False
        prev_idx = order_pos.get(id(prev_element), -1)
        curr_idx = order_pos.get(id(element), -1)
        if prev_idx < 0 or curr_idx <= prev_idx:
            return False
        return any(node.tag == 'br' for node in order[prev_idx + 1:curr_idx])

    def _group_embedded_t_matches(self, matched, parent_map):
        by_element = {}
        by_sense = {}
        for element in matched:
            parent = parent_map.get(element)
            if parent is not None and parent.tag == 'ex':
                current = parent
                sense = None
                while current is not None:
                    if current.tag == 'sense':
                        sense = current
                        break
                    current = parent_map.get(current)
                if sense is not None:
                    sid = id(sense)
                    group = by_sense.get(sid)
                    if group is None:
                        group = {'sense': sense, 'elements': []}
                        by_sense[sid] = group
                    group['elements'].append(element)
                    by_element[id(element)] = group
        return by_element, by_sense

    def _build_embedded_t_preview(self, group, pattern, parent_map, root, headword):
        sense = group['sense']
        elements = group['elements']

        parts = [self._sense_number_html(sense)]
        main_t = sense.find('t')
        if main_t is not None:
            parts.append(f'<span class="t">{self._element_preview_content(main_t, "t", pattern)}</span>')
            parts.append(main_t.tail or ' ')

        seen_ex = set()
        sep = ''
        for element in elements:
            ex_el = parent_map.get(element)
            if ex_el is None or id(ex_el) in seen_ex:
                continue
            seen_ex.add(id(ex_el))
            ex_content = self._element_preview_content(ex_el, 'ex', pattern)
            parts.append(sep)
            parts.append(f'<span class="g">{ex_content}</span>')
            sep = ex_el.tail or ' '

        preview_html = ''.join(parts)
        first = elements[0]
        preview_hw, preview_sort = self._preview_hw_fields(first, parent_map, root, headword)
        return {
            'headword': preview_hw,
            'sort_headword': preview_sort,
            'preview_html': f'<span class="t">{preview_html}</span>',
            'rank': self._compute_t_match_rank(first, pattern, 't'),
        }

    def _format_child_for_preview(self, child):
        child_copy = copy.deepcopy(child)
        child_copy.tail = None
        wrapper = ElementTree.Element('_wrapper')
        wrapper.append(child_copy)
        return process_element(wrapper, None)

    def _should_exclude_from_highlight(self, child, tag):
        if child.tag in ('src', 'st'):
            return True
        if tag == 't':
            if child.tag == 'see':
                return True
            for attr_name, attr_val in (('lang', 'vl'), ('excl', None)):
                if attr_val is None:
                    if attr_name in child.attrib:
                        return True
                elif child.get(attr_name) == attr_val:
                    return True
            return False
        if tag == 'ex' and child.get('lang') == 'ru':
            return True
        return False

    def _build_preview_html(self, element, tag, pattern, parent_map):
        highlighted = self._element_preview_content(element, tag, pattern)
        if tag in ('t', 'ex'):
            highlighted = self._add_sibling_context(highlighted, element, pattern, parent_map, tag)

        tag_class = 't' if tag == 't' else 'g'
        return f'<span class="{tag_class}">{highlighted}</span>'

    def _element_preview_content(self, element, tag, pattern):
        segments = []
        excluded_fragments = []
        layout = []
        if element.text:
            segments.append(element.text)
            layout.append(('seg', len(segments) - 1))
        for child in element:
            child_html = self._format_child_for_preview(child)
            if self._should_exclude_from_highlight(child, tag):
                excluded_fragments.append(child_html)
                layout.append(('excl', len(excluded_fragments) - 1))
            else:
                segments.append(child_html)
                layout.append(('seg', len(segments) - 1))
            if child.tail:
                segments.append(child.tail)
                layout.append(('seg', len(segments) - 1))
        html_parts = []
        for entry_type, idx in layout:
            if entry_type == 'seg':
                html_parts.append(segments[idx])
            else:
                html_parts.append(f'<span class="{_EXCLUDED_HIGHLIGHT_CLASS}">{excluded_fragments[idx]}</span>')
        return self.apply_highlight(
            ''.join(html_parts), pattern,
            normalize=(tag == 't'),
            exclude_classes=[_EXCLUDED_HIGHLIGHT_CLASS],
        )

    def _add_sibling_context(self, highlighted, element, pattern, parent_map, tag):
        parent = parent_map.get(element)
        if parent is not None:
            siblings = list(parent)
            try:
                idx = siblings.index(element)
            except ValueError:
                idx = -1
            if tag == 't':
                if idx > 0:
                    prev_sib = siblings[idx - 1]
                    if prev_sib.tag == 'ex' and prev_sib.tail and '—' in prev_sib.tail:
                        ex_fmt = process_element(prev_sib, None)
                        context = f'<span class="g">{ex_fmt}</span>—'
                        if idx >= 2 and siblings[idx - 2].tag == 't':
                            prev_t = siblings[idx - 2]
                            prev_t_fmt = self._element_preview_content(prev_t, 't', pattern)
                            context = f'<span class="t">{prev_t_fmt}</span>' + (prev_t.tail or '') + context
                        highlighted = context + highlighted

                sep = element.tail or ''
                i = idx + 1
                while i + 1 < len(siblings):
                    ex_sib = siblings[i]
                    t_sib = siblings[i + 1]
                    if not (ex_sib.tag == 'ex' and ex_sib.tail and '—' in ex_sib.tail
                            and t_sib.tag == 't'):
                        break
                    ex_fmt = process_element(ex_sib, None)
                    t_fmt = self._element_preview_content(t_sib, 't', pattern)
                    highlighted += sep + f'<span class="g">{ex_fmt}</span>—<span class="t">{t_fmt}</span>'
                    sep = t_sib.tail or ''
                    i += 2

                sense_num = ''
                crossed_sub_headword = False
                current = element
                while current in parent_map:
                    current = parent_map[current]
                    if current.tag == 'd':
                        crossed_sub_headword = True
                        continue
                    if current.tag == 'sense' and current.attrib:
                        if not crossed_sub_headword:
                            sense_num = self._sense_number_html(current)
                        break
                highlighted = sense_num + highlighted
            elif tag == 'ex' and element.tail and '—' in element.tail and idx + 1 < len(siblings):
                next_sib = siblings[idx + 1]
                if next_sib.tag == 't':
                    t_fmt = process_element(next_sib, None)
                    highlighted += f'<span class="t">—{t_fmt}</span>'
        return highlighted

    @staticmethod
    def _restore_saved_blocks(html, saved_blocks):
        if not saved_blocks:
            return html
        placeholder = re.compile(r'\x00A(\d+)\x00')
        for _ in range(2):
            html = placeholder.sub(lambda m: saved_blocks[int(m.group(1))], html)
        return html

    @staticmethod
    def _sense_number_html(sense):
        num = sense.find('n')
        if num is None:
            num = sense.find('b')
        if num is None:
            return ''
        num_text = ''.join(num.itertext()).strip()
        return f'<span class="{num.tag}">{num_text}</span> '

    def apply_highlight(self, formatted_html, pattern, normalize=True, exclude_classes=None):
        all_saved = []
        protected = formatted_html

        a_pat = re.compile(r'(<a\s[^>]*>.*?</a>)', re.DOTALL)
        def _save_a(m):
            all_saved.append(m.group(1))
            return f'\x00A{len(all_saved)-1}\x00'
        protected = a_pat.sub(_save_a, protected)

        if exclude_classes:
            for cls in exclude_classes:
                protected = self._protect_class_blocks(protected, cls, all_saved)

        parts = re.split(r'(<[^>]*>)', protected)

        expanded = []
        for part in parts:
            if not part.startswith('<') and '\x00' in part:
                for chunk in re.split(r'(\x00[^\x00]*\x00)', part):
                    if chunk:
                        expanded.append(chunk)
            else:
                expanded.append(part)
        parts = expanded

        text_ranges = []
        concat_pos = 0
        for i, part in enumerate(parts):
            if not part.startswith('<') and part and '\x00' not in part:
                text_ranges.append((concat_pos, i))
                concat_pos += len(part)

        if not text_ranges:
            return self._restore_saved_blocks(''.join(parts), all_saved)

        concatenated = ''.join(parts[r[1]] for r in text_ranges)
        normalized = normalize_jo(concatenated) if normalize else concatenated

        matches = list(pattern.finditer(normalized))

        highlights_per_part = {}
        for m in matches:
            ms, me = m.start(), m.end()
            for concat_start, part_idx in text_ranges:
                part_len = len(parts[part_idx])
                concat_end = concat_start + part_len
                if me <= concat_start or ms >= concat_end:
                    continue
                local_start = max(ms - concat_start, 0)
                local_end = min(me - concat_start, part_len)
                highlights_per_part.setdefault(part_idx, []).append((local_start, local_end))

        for part_idx, ranges in highlights_per_part.items():
            ranges.sort()
            merged = []
            for s, e in ranges:
                if merged and s <= merged[-1][1]:
                    merged[-1] = (merged[-1][0], max(merged[-1][1], e))
                else:
                    merged.append((s, e))
            part = parts[part_idx]
            result_parts = []
            last = 0
            for s, e in merged:
                result_parts.append(part[last:s])
                result_parts.append(
                    f'<span class="search-highlight">{part[s:e]}</span>'
                )
                last = e
            result_parts.append(part[last:])
            parts[part_idx] = ''.join(result_parts)

        return self._restore_saved_blocks(''.join(parts), all_saved)

    def _protect_class_blocks(self, html, class_name, saved_list):
        pattern = re.compile(
            r'(<span[^>]*class="[^"]*' + re.escape(class_name) + r'[^"]*"[^>]*>)'
        )
        result = []
        pos = 0
        while pos < len(html):
            m = pattern.search(html, pos)
            if not m:
                result.append(html[pos:])
                break
            result.append(html[pos:m.start()])
            start = m.start()
            depth = 1
            i = m.end()
            while depth > 0 and i < len(html):
                next_open = html.find('<span', i)
                next_close = html.find('</span>', i)
                if next_close == -1:
                    i = len(html)
                    break
                if next_open != -1 and next_open < next_close:
                    depth += 1
                    i = next_open + len('<span')
                else:
                    depth -= 1
                    i = next_close + len('</span>')
            saved_list.append(html[start:i])
            result.append(f'\x00A{len(saved_list)-1}\x00')
            pos = i
        return ''.join(result)

    def _enclosing_sense(self, element, parent_map):
        current = element
        while current in parent_map:
            current = parent_map[current]
            if current.tag == 'sense':
                return current
        return None

    def _preview_hw_fields(self, element, parent_map, root, headword):
        display = None
        sort = None
        current = element
        while current in parent_map:
            current = parent_map[current]
            if current.tag == 'd':
                variants = d_hw_variants(current)
                if variants:
                    display = '|'.join(variants)
                    sort_variants = d_hw_variants(current, exclude_n=True)
                    sort = '|'.join(sort_variants) if sort_variants else display
                    return display, sort
        if display is None:
            element_sense = self._enclosing_sense(element, parent_map)
            relevant = []
            relevant_sort = []
            for h in root.findall('.//hw'):
                text = ''.join(h.itertext()).strip()
                if not text:
                    continue
                hw_sense = self._enclosing_sense(h, parent_map)
                if hw_sense is None or hw_sense is element_sense:
                    relevant.append(text)
                    relevant_sort.append(hw_text_excluding_n(h).strip() or text)
            if relevant:
                if root.find('.//d') is None:
                    return '|'.join(relevant), '|'.join(relevant_sort)
                return relevant[0], relevant_sort[0]
        return headword, headword

    def _compute_t_match_rank(self, t_element, pattern, tag):
        candidates = []
        element_level = t_element.get('lvl')
        element_text = content_text(t_element, tag)
        if element_text:
            clean = index_text(element_text, tag)
            m = pattern.search(clean)
            if m:
                candidates.append(self._tier_for_match(m, clean, element_level))
        for tp in t_element:
            if tp.tag == 'tp':
                tp_text = content_text(tp, None)
                if tp_text:
                    clean = index_text(tp_text, tag)
                    m = pattern.search(clean)
                    if m:
                        candidates.append(self._tier_for_match(m, clean, tp.get('lvl')))
        if not candidates:
            return 2
        return min(candidates)

    def _tier_for_match(self, m, clean, level):
        if level == '1':
            exact = m.start() == 0 and m.end() == len(clean)
            return 0 if exact else 1
        return 2

    def get_entry_by_headword(self, headword):
        conn = self._get_connection()
        cursor = conn.cursor()
        search_headword = remove_accents(headword).lower()
        cursor.execute("""
            SELECT id, headword, full_entry, entry_link, source_file
            FROM dictionary
            WHERE normalized_headword = ?
        """, (search_headword,))
        result = cursor.fetchone()
        if result:
            return result + (None,)
        cursor.execute("""
            SELECT id, headword, full_entry, entry_link, source_file
            FROM dictionary
        """)
        for row in cursor.fetchall():
            if remove_accents(row[1]).lower() == search_headword:
                return row + (None,)
        cursor.execute("""
            SELECT dictionary.id, sub_headwords.headword, dictionary.full_entry, dictionary.entry_link, dictionary.source_file
            FROM sub_headwords
            JOIN dictionary ON sub_headwords.main_entry_id = dictionary.id
            WHERE sub_headwords.normalized_headword = ?
        """, (search_headword,))
        result = cursor.fetchone()
        if result:
            return result + (None,)
        cursor.execute("""
            SELECT dictionary.id, sub_headwords.headword, dictionary.full_entry, dictionary.entry_link, dictionary.source_file
            FROM sub_headwords
            JOIN dictionary ON sub_headwords.main_entry_id = dictionary.id
        """)
        for row in cursor.fetchall():
            if remove_accents(row[1]).lower() == search_headword:
                return row + (None,)
        return None, None, None, None, None, None

    def get_entry_by_link(self, entry_link):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, headword, full_entry, entry_link, source_file
            FROM dictionary
            WHERE entry_link = ?
        """, (entry_link,))
        result = cursor.fetchone()
        return result + (None,) if result else None

    def get_entry_row(self, entry_id):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, headword, full_entry, entry_link, source_file
            FROM dictionary
            WHERE id = ?
        """, (entry_id,))
        result = cursor.fetchone()
        return result + (None,) if result else None