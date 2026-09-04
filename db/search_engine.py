import copy
import re
import sqlite3
import xml.etree.ElementTree as ElementTree
from utils.accent_utils import remove_accents, normalize_jo, get_text_excluding_src
from utils.case_utils import compile_search_regex
from format.entry_formatter import _process_element


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
        return [r + (None,) for r in self._search_headwords("")]

    def _search_headwords(self, text):
        conn = self._get_connection()
        cursor = conn.cursor()

        clean_text = remove_accents(text.strip())

        if clean_text == "":
            cursor.execute("""
                SELECT id, headword, full_entry, entry_link, source_file
                FROM dictionary
                ORDER BY normalized_headword
            """)
            main_results = cursor.fetchall()

            cursor.execute("""
                SELECT dictionary.id, sub_headwords.headword, dictionary.full_entry, dictionary.entry_link, dictionary.source_file
                FROM sub_headwords
                JOIN dictionary ON sub_headwords.main_entry_id = dictionary.id
                ORDER BY sub_headwords.normalized_headword
            """)
            sub_results = cursor.fetchall()

            combined = main_results + sub_results
            unique = list({(result[0], result[1]): result for result in combined}.values())
            unique.sort(key=lambda x: x[1].lower())
            return [r for r in unique if r[1] != "!SOURCES"]

        pattern = compile_search_regex(clean_text, exact_words=text.endswith(' '))

        sql_text = clean_text.lower()
        sql_pattern = sql_text.replace('?', '_').replace('*', '%')
        sql_pattern = '%' + sql_pattern.replace(' ', '%') + '%'

        cursor.execute("""
            SELECT id, headword, full_entry, entry_link, source_file
            FROM dictionary
            WHERE normalized_headword LIKE ?
            ORDER BY normalized_headword
        """, (sql_pattern,))
        main_results = cursor.fetchall()

        cursor.execute("""
            SELECT dictionary.id, sub_headwords.headword, dictionary.full_entry, dictionary.entry_link, dictionary.source_file
            FROM sub_headwords
            JOIN dictionary ON sub_headwords.main_entry_id = dictionary.id
            WHERE sub_headwords.normalized_headword LIKE ?
            ORDER BY sub_headwords.normalized_headword
        """, (sql_pattern,))
        sub_results = cursor.fetchall()

        combined = main_results + sub_results
        unique = list({(result[0], result[1]): result for result in combined}.values())
        unique = [r for r in unique if pattern.search(remove_accents(r[1]))]
        unique.sort(key=lambda x: x[1].lower())
        return unique

    def _search_via_index(self, text, tag_type):
        use_normalize = tag_type == 't'
        clean = normalize_jo(remove_accents(text.strip().lower())) if use_normalize else remove_accents(text.strip().lower())
        pattern = compile_search_regex(clean, exact_words=text.endswith(' '))

        sql_pattern = clean.replace('?', '_').replace('*', '%')
        sql_pattern = '%' + sql_pattern + '%'

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

        cursor.execute(f"""
            SELECT id, headword, full_entry, entry_link, source_file FROM dictionary
            WHERE id IN ({placeholders})
        """, entry_ids)
        main_results = cursor.fetchall()

        cursor.execute(f"""
            SELECT dictionary.id, sub_headwords.headword, dictionary.full_entry, dictionary.entry_link, dictionary.source_file
            FROM sub_headwords
            JOIN dictionary ON sub_headwords.main_entry_id = dictionary.id
            WHERE dictionary.id IN ({placeholders})
            ORDER BY sub_headwords.normalized_headword
        """, entry_ids)
        sub_results = cursor.fetchall()

        combined = main_results + sub_results
        unique = list({(r[0], r[1]): r for r in combined}.values())
        self._annotate_content_matches(unique, tag_type, pattern)
        return [r for r in unique if r[4]]

    def _search_translations(self, text):
        return self._search_via_index(text, 't')

    def _search_examples(self, text):
        return self._search_via_index(text, 'ex')

    def _annotate_content_matches(self, results, tag, pattern):
        for i, result in enumerate(results):
            entry_id, headword, full_entry, entry_link = result[:4]
            clean_headword = remove_accents(headword)
            root = ElementTree.fromstring(full_entry)
            previews = self._find_content_matches(root, headword, tag, pattern, full_entry)
            previews = [p for p in previews if remove_accents(p['headword']) == clean_headword or clean_headword in remove_accents(p['headword']).split('|')]
            results[i] = result[:4] + (previews,)

    def _find_content_matches(self, root, headword, tag, pattern, xml_data=None):
        parent_map = {c: p for p in root.iter() for c in p}
        previews = []
        prev_element = None
        last_xml_end = 0
        for element in root.iter(tag):
            search_text = get_text_excluding_src(
                element,
                extra_exclude={'see'} if tag == 't' else None,
                skip_attrs={'lang': 'vl', 'excl': None} if tag == 't' else (
                    {'lang': 'ru'} if tag == 'ex' else None
                )
            )
            if not search_text:
                continue
            normalized_search = normalize_jo(remove_accents(search_text)) if tag == 't' else remove_accents(search_text)
            if not pattern.search(normalized_search):
                continue

            paragraph_break = self._detect_preview_break(prev_element, element, xml_data, last_xml_end)

            preview_hw = self._find_closest_hw(root, element)
            if preview_hw is None:
                main_hw = root.find('.//hw')
                preview_hw = ''.join(main_hw.itertext()).strip() if main_hw is not None else headword

            rank, word_pos, word_len = self._compute_t_match_rank(element, pattern, tag)

            preview_html = self._build_preview_html(element, tag, pattern, parent_map)
            previews.append({
                'headword': preview_hw,
                'preview_html': preview_html,
                'paragraph_break': paragraph_break,
                'rank': rank,
                'word_pos': word_pos,
                'word_len': word_len,
            })
            prev_element = element
        return previews

    def _detect_preview_break(self, prev_element, element, xml_data, last_xml_end):
        if prev_element is None or xml_data is None:
            return False
        curr_xml = ElementTree.tostring(element, encoding='unicode')
        curr_pos = xml_data.find(curr_xml, last_xml_end)
        if curr_pos == -1:
            return False
        between = xml_data[last_xml_end:curr_pos]
        return '<br' in between

    def _format_child_for_preview(self, child):
        child_copy = copy.deepcopy(child)
        child_copy.tail = None
        wrapper = ElementTree.Element('_wrapper')
        wrapper.append(child_copy)
        return _process_element(wrapper, None)

    def _should_exclude_from_highlight(self, child, tag):
        if child.tag in ('src', 'st'):
            return True
        if tag == 't' and child.tag == 'see':
            return True
        if tag == 't':
            for attr_name, attr_val in (('lang', 'vl'), ('excl', None)):
                if attr_val is None:
                    if attr_name in child.attrib:
                        return True
                elif child.get(attr_name) == attr_val:
                    return True
        if tag == 'ex' and child.get('lang') == 'ru':
            return True
        return False

    def _build_preview_html(self, element, tag, pattern, parent_map):
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
                html_parts.append(excluded_fragments[idx])
        highlighted = self._apply_highlight(''.join(html_parts), pattern, normalize=(tag == 't'))

        if tag == 't':
            highlighted = self._add_translation_context(highlighted, element, parent_map)
        elif tag == 'ex' and element.tail and '—' in element.tail:
            highlighted = self._add_example_context(highlighted, element, parent_map)

        tag_class = 't' if tag == 't' else 'g'
        return f'<span class="{tag_class}">{highlighted}</span>'

    def _add_translation_context(self, highlighted, element, parent_map):
        parent = parent_map.get(element)
        if parent is not None:
            siblings = list(parent)
            try:
                idx = siblings.index(element)
            except ValueError:
                idx = -1
            if idx > 0:
                prev_sib = siblings[idx - 1]
                if prev_sib.tag == 'ex' and prev_sib.tail and '—' in prev_sib.tail:
                    ex_fmt = _process_element(prev_sib, None)
                    highlighted = f'<span class="g">{ex_fmt}</span>—' + highlighted

        b_html = ''
        current = element
        while current in parent_map:
            current = parent_map[current]
            if current.tag == 'sense' and current.attrib:
                sense_b = current.find('b')
                if sense_b is not None:
                    b_text = ''.join(sense_b.itertext()).strip()
                    b_html = f'<span class="b">{b_text}</span> '
                break
        highlighted = b_html + highlighted
        return highlighted

    def _add_example_context(self, highlighted, element, parent_map):
        parent = parent_map.get(element)
        if parent is not None:
            siblings = list(parent)
            try:
                idx = siblings.index(element)
            except ValueError:
                idx = -1
            if idx + 1 < len(siblings):
                next_sib = siblings[idx + 1]
                if next_sib.tag == 't':
                    t_fmt = _process_element(next_sib, None)
                    highlighted += f'<span class="t">—{t_fmt}</span>'
        return highlighted

    def _apply_highlight(self, formatted_html, pattern, normalize=True, exclude_classes=None):
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

        text_ranges = []
        concat_pos = 0
        for i, part in enumerate(parts):
            if not part.startswith('<') and part and '\x00' not in part:
                text_ranges.append((concat_pos, i))
                concat_pos += len(part)

        if not text_ranges:
            result = ''.join(parts)
            for _ in range(2):
                for j, block in enumerate(all_saved):
                    result = result.replace(f'\x00A{j}\x00', block)
            return result

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
                    f'<span style="background-color: #FFF9C4;">{part[s:e]}</span>'
                )
                last = e
            result_parts.append(part[last:])
            parts[part_idx] = ''.join(result_parts)

        result = ''.join(parts)
        for _ in range(2):
            for j, block in enumerate(all_saved):
                result = result.replace(f'\x00A{j}\x00', block)
        return result

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
                    i = next_open + 5
                else:
                    depth -= 1
                    i = next_close + 7
            saved_list.append(html[start:i])
            result.append(f'\x00A{len(saved_list)-1}\x00')
            pos = i
        return ''.join(result)

    def _find_closest_hw(self, root, element):
        parent_map = {c: p for p in root.iter() for c in p}
        match_sense = None
        current = element
        while current in parent_map:
            current = parent_map[current]
            if current.tag == 'sense' and current.attrib:
                match_sense = current
                break
        if match_sense is not None:
            hw_attr = match_sense.get('hw')
            if hw_attr:
                return hw_attr
        all_elements = list(root.iter())
        try:
            element_index = all_elements.index(element)
        except ValueError:
            return None
        if match_sense is None:
            for i in range(element_index - 1, -1, -1):
                el = all_elements[i]
                if el.tag == 'hw':
                    return ''.join(el.itertext()).strip()
            return None
        for i in range(element_index - 1, -1, -1):
            el = all_elements[i]
            if el.tag == 'hw':
                current = el
                while current in parent_map:
                    current = parent_map[current]
                    if current is match_sense:
                        return ''.join(el.itertext()).strip()
                    if current.tag == 'sense' and current.attrib:
                        break
                else:
                    return ''.join(el.itertext()).strip()
        return None

    def _compute_t_match_rank(self, t_element, pattern, tag):
        if tag != 't':
            return (7, 0, 0)
        lvl = t_element.get('lvl')
        tp_children = [child for child in t_element if child.tag == 'tp']
        if not lvl and not tp_children:
            return (7, 0, 0)
        candidates = []
        if lvl:
            candidates.append(self._rank_from_level(t_element, lvl, pattern))
        for tp in tp_children:
            candidates.append(self._rank_from_tp(tp, pattern))
        return min(candidates)

    def _rank_from_level(self, element, lvl, pattern):
        text = get_text_excluding_src(element)
        clean = normalize_jo(remove_accents(text.lower()))
        m = pattern.search(clean)
        if not m:
            return (7, 0, 0)
        is_exact = m.start() == 0 and m.end() == len(clean)
        base = 1 if lvl == '1' else 3 if lvl == '2' else 5
        if is_exact:
            return (base, 0, 0)
        return (base + 1,) + self._compute_portion_info(text, clean, m)

    def _rank_from_tp(self, tp, pattern):
        lvl = tp.get('lvl', '1')
        text = get_text_excluding_src(tp)
        clean = normalize_jo(remove_accents(text.lower()))
        m = pattern.search(clean)
        if not m:
            return (7, 0, 0)
        is_exact = m.start() == 0 and m.end() == len(clean)
        base = 1 if lvl == '1' else 3 if lvl == '2' else 5
        if is_exact:
            return (base, 0, 0)
        return (base + 1,) + self._compute_portion_info(text, clean, m)

    def _compute_portion_info(self, orig_text, clean_text, match):
        orig_words = orig_text.split()
        clean_words = clean_text.split()
        if not clean_words:
            return (1, 0)
        offset = 0
        for i, cw in enumerate(clean_words):
            word_end = offset + len(cw)
            if match.start() < word_end:
                ow = orig_words[i] if i < len(orig_words) else cw
                clean_len = len(re.sub(r'\W', '', ow, flags=re.UNICODE))
                return (0 if i == 0 else 1, clean_len)
            offset = word_end + 1
        return (1, 0)

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
            return result[0], result[1], result[2], result[3], result[4]
        return None, None, None, None, None

    def get_entry_by_id(self, entry_link):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, headword, full_entry, entry_link, source_file
            FROM dictionary
            WHERE entry_link = ?
        """, (entry_link,))
        result = cursor.fetchone()
        return result
