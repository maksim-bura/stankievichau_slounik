import sqlite3
import xml.etree.ElementTree as ElementTree
from collections import OrderedDict

from dictionary_app.utils.normalize_headword import normalize_jo_to_je
from dictionary_app.utils.remove_accents import remove_accents
from dictionary_app.utils.extract_content_text import index_text
from dictionary_app.utils.compile_search_regex import compile_search_regex
from dictionary_app.utils.xml_schema import ATTR_KEEP_ACC
from dictionary_app.format.highlight_formatter import HighlightFormatter


_PARSED_CACHE_MAX_SIZE = 512
_PREVIEW_CACHE_MAX_SIZE = 2048
_TRIGRAM_MIN_SPAN = 3

_EMPTY_ENTRY_ROW = (None, None, None, None, None, None, None)

_ENTRY_SELECT_SQL = (
    "SELECT dictionary.id, dictionary.headword, entry_body.xml, "
    "dictionary.entry_link, dictionary.source_file, dictionary.keep_acc "
    "FROM dictionary LEFT JOIN entry_body ON entry_body.id = dictionary.id "
)

_SUB_MATCH_SELECT_SQL = (
    "SELECT dictionary.id, dictionary.headword, entry_body.xml, "
    "dictionary.entry_link, dictionary.source_file, dictionary.keep_acc, "
    "sub_headwords.headword, sub_headwords.keep_acc "
    "FROM sub_headwords "
    "JOIN dictionary ON sub_headwords.main_entry_id = dictionary.id "
    "LEFT JOIN entry_body ON entry_body.id = dictionary.id "
)

_DICTIONARY_HEADWORD_SQL = (
    "SELECT id, headword, NULL AS full_entry, entry_link, source_file, "
    "sort_headword, normalized_headword, keep_acc, hw_xml_id, collation_key "
    "FROM dictionary "
)

_SUB_HEADWORD_SQL = (
    "SELECT dictionary.id, sub_headwords.headword, NULL AS full_entry, "
    "COALESCE(sub_headwords.link, dictionary.entry_link), dictionary.source_file, "
    "sub_headwords.sort_headword, sub_headwords.normalized_headword, "
    "sub_headwords.keep_acc, sub_headwords.hw_xml_id, sub_headwords.collation_key "
    "FROM sub_headwords "
    "JOIN dictionary ON sub_headwords.main_entry_id = dictionary.id "
)

_HEADWORD_ROWS_SQL = (
    _DICTIONARY_HEADWORD_SQL + "{dictionary_where} UNION ALL "
    + _SUB_HEADWORD_SQL + "{sub_headwords_where}"
)

_ENTRY_ROWS_SQL = (
    _ENTRY_SELECT_SQL + "WHERE dictionary.id IN ({placeholders}) UNION "
    "SELECT dictionary.id, sub_headwords.headword, entry_body.xml, "
    "COALESCE(sub_headwords.link, dictionary.entry_link), dictionary.source_file, "
    "sub_headwords.keep_acc "
    "FROM sub_headwords "
    "JOIN dictionary ON sub_headwords.main_entry_id = dictionary.id "
    "LEFT JOIN entry_body ON entry_body.id = dictionary.id "
    "WHERE dictionary.id IN ({placeholders})"
)


class SearchEngine:
    def __init__(self, database_path):
        self.database_path = database_path
        self._connection = None
        self._parsed_cache = OrderedDict()
        self._preview_cache = OrderedDict()
        self._highlight_formatter = HighlightFormatter()

    def _get_connection(self):
        if self._connection is None:
            self._connection = sqlite3.connect(self.database_path)
        return self._connection

    def close(self):
        if self._connection is not None:
            self._connection.close()
            self._connection = None
        self._parsed_cache.clear()
        self._preview_cache.clear()

    def invalidate_entry(self, entry_id):
        self._parsed_cache.pop(entry_id, None)
        self._preview_cache.clear()

    def get_parsed_entry(self, entry_id, xml_string=None):
        if entry_id in self._parsed_cache:
            self._parsed_cache.move_to_end(entry_id)
            return self._parsed_cache[entry_id]

        if xml_string is None:
            return None

        root = ElementTree.fromstring(xml_string)
        self._parsed_cache[entry_id] = root
        while len(self._parsed_cache) > _PARSED_CACHE_MAX_SIZE:
            self._parsed_cache.popitem(last=False)
        return root

    def get_main_headword(self, entry_id, xml_string=None):
        root = self.get_parsed_entry(entry_id, xml_string)
        element = root.find('.//hw') if root is not None else None
        if element is None:
            return ""
        return ''.join(element.itertext()).strip()

    def get_main_headword_display(self, entry_id, xml_string=None):
        root = self.get_parsed_entry(entry_id, xml_string)
        element = root.find('.//hw') if root is not None else None
        if element is None:
            return ""
        text = ''.join(element.itertext()).strip()
        if element.get(ATTR_KEEP_ACC) is not None:
            return text
        return remove_accents(text)

    def search(self, text, search_in_headwords=True, search_in_translations=False, search_in_examples=False):
        if not text.strip():
            return self._search_headwords("")
        if search_in_translations and search_in_examples:
            raise ValueError("combined translations+examples search is not implemented")
        if not search_in_headwords:
            if search_in_translations:
                return self._search_translations(text)
            if search_in_examples:
                return self._search_examples(text)
        return self._search_headwords(text)

    def _search_headwords(self, text):
        conn = self._get_connection()
        cursor = conn.cursor()

        clean_text = remove_accents(text.strip())

        if clean_text == "":
            cursor.execute(_HEADWORD_ROWS_SQL.format(
                dictionary_where='', sub_headwords_where=''))
            unique = cursor.fetchall()
            unique.sort(key=lambda r: r[9])
            return [self._row_result(r) for r in unique]

        pattern = compile_search_regex(text.strip(), exact_words=text.endswith(' '))

        dict_ids, sub_ids = self._candidate_headword_ids(clean_text)
        if dict_ids or sub_ids:
            rows = []
            if dict_ids:
                placeholders = ','.join(['?'] * len(dict_ids))
                cursor.execute(
                    _DICTIONARY_HEADWORD_SQL + f"WHERE id IN ({placeholders})",
                    dict_ids)
                rows.extend(cursor.fetchall())
            if sub_ids:
                placeholders = ','.join(['?'] * len(sub_ids))
                cursor.execute(
                    _SUB_HEADWORD_SQL + f"WHERE sub_headwords.id IN ({placeholders})",
                    sub_ids)
                rows.extend(cursor.fetchall())
            unique = [r for r in rows if pattern.search(r[1])]
            unique.sort(key=lambda r: r[9])
            return [self._row_result(r) for r in unique]

        sql_pattern = self._like_pattern(clean_text.lower(), collapse_spaces=True)

        cursor.execute(_HEADWORD_ROWS_SQL.format(
            dictionary_where='WHERE normalized_headword LIKE ?',
            sub_headwords_where='WHERE sub_headwords.normalized_headword LIKE ?',
        ), (sql_pattern, sql_pattern))
        unique = cursor.fetchall()

        unique = [r for r in unique if pattern.search(r[1])]
        unique.sort(key=lambda r: r[9])
        return [self._row_result(r) for r in unique]

    @staticmethod
    def _row_result(r):
        return (r[0], r[1], r[2], r[3], r[4], None, r[7])

    def _candidate_headword_ids(self, clean_text):
        span = self._alphanumeric_span(clean_text)
        if len(span) < _TRIGRAM_MIN_SPAN:
            return [], []
        try:
            cursor = self._get_connection().cursor()
            cursor.execute(
                "SELECT rowid FROM headword_fts WHERE headword_fts MATCH ?",
                (f'"{span}"',),
            )
            dict_ids = [row[0] for row in cursor.fetchall()]
            cursor.execute(
                "SELECT rowid FROM sub_headword_fts WHERE sub_headword_fts MATCH ?",
                (f'"{span}"',),
            )
            sub_ids = [row[0] for row in cursor.fetchall()]
            return dict_ids, sub_ids
        except sqlite3.OperationalError:
            return [], []

    @staticmethod
    def _like_pattern(text, collapse_spaces=False):
        pattern = text.replace('?', '_').replace('*', '%')
        if collapse_spaces:
            pattern = pattern.replace(' ', '%')
        return '%' + pattern + '%'

    def _search_via_index(self, text, tag_type):
        clean = index_text(text.strip(), tag_type)
        pattern_text = remove_accents(text.strip())
        if tag_type == 't':
            pattern_text = normalize_jo_to_je(pattern_text)
        pattern = compile_search_regex(pattern_text, exact_words=text.endswith(' '))

        entry_ids = self._candidate_entry_ids(clean, tag_type)
        if not entry_ids:
            return []

        placeholders = ','.join(['?'] * len(entry_ids))
        params = entry_ids + entry_ids

        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(_ENTRY_ROWS_SQL.format(placeholders=placeholders), params)
        unique = cursor.fetchall()
        self._annotate_content_matches(unique, tag_type, pattern)
        return [r for r in unique if r[5]]

    def _candidate_entry_ids(self, clean, tag_type):
        conn = self._get_connection()
        cursor = conn.cursor()
        span = self._alphanumeric_span(clean)
        if len(span) >= _TRIGRAM_MIN_SPAN:
            try:
                cursor.execute(
                    f"SELECT rowid FROM content_fts_{tag_type} WHERE content_fts_{tag_type} MATCH ?",
                    (f'"{span}"',),
                )
                rowids = [r[0] for r in cursor.fetchall()]
            except sqlite3.OperationalError:
                rowids = []
            if rowids:
                placeholders = ','.join(['?'] * len(rowids))
                cursor.execute(
                    f"SELECT DISTINCT entry_id FROM content_index WHERE id IN ({placeholders})",
                    rowids,
                )
                return [r[0] for r in cursor.fetchall()]
        sql_pattern = self._like_pattern(clean)
        cursor.execute("""
            SELECT DISTINCT entry_id FROM content_index
            WHERE searchable_text LIKE ? AND tag_type = ?
        """, (sql_pattern, tag_type))
        return [r[0] for r in cursor.fetchall()]

    @staticmethod
    def _alphanumeric_span(text):
        best = ''
        current = []
        for ch in text:
            if ch.isalnum():
                current.append(ch)
            else:
                if len(current) > len(best):
                    best = ''.join(current)
                current = []
        if len(current) > len(best):
            best = ''.join(current)
        return best

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
            keep_acc = result[5]
            if entry_id not in previews_by_entry:
                cache_key = (entry_id, headword, keep_acc, tag, pattern.pattern)
                cached = self._preview_cache.get(cache_key)
                if cached is not None:
                    self._preview_cache.move_to_end(cache_key)
                    previews_by_entry[entry_id] = cached
                else:
                    root = self.get_parsed_entry(entry_id, full_entry)
                    previews = self._highlight_formatter.find_content_matches(root, headword, tag, pattern, keep_acc)
                    self._preview_cache[cache_key] = previews
                    while len(self._preview_cache) > _PREVIEW_CACHE_MAX_SIZE:
                        self._preview_cache.popitem(last=False)
                    previews_by_entry[entry_id] = previews
            results[i] = result[:5] + (previews_by_entry[entry_id], result[5])

    def apply_highlight(self, formatted_html, pattern, normalize=True, exclude_classes=None):
        return self._highlight_formatter.apply_highlight(
            formatted_html, pattern,
            normalize=normalize, exclude_classes=exclude_classes,
        )

    def _get_entry_row(self, where_clause, param):
        cursor = self._get_connection().cursor()
        cursor.execute(
            _ENTRY_SELECT_SQL + "WHERE " + where_clause,
            (param,),
        )
        result = cursor.fetchone()
        if not result:
            return _EMPTY_ENTRY_ROW
        return (result[0], result[1], result[2], result[3], result[4], None, result[5])

    def _get_exact_headword(self, headword):
        cursor = self._get_connection().cursor()
        rows = []
        cursor.execute(
            _ENTRY_SELECT_SQL + "WHERE dictionary.headword = ?",
            (headword,),
        )
        for row in cursor.fetchall():
            rows.append((row[0], row[1], row[2], row[3], row[4], None, row[5]))
        cursor.execute(
            "SELECT dictionary.id, sub_headwords.headword, entry_body.xml, "
            "sub_headwords.link, dictionary.source_file, sub_headwords.keep_acc "
            "FROM sub_headwords JOIN dictionary ON sub_headwords.main_entry_id = dictionary.id "
            "LEFT JOIN entry_body ON entry_body.id = dictionary.id "
            "WHERE sub_headwords.headword = ?",
            (headword,),
        )
        for row in cursor.fetchall():
            rows.append((row[0], row[1], row[2], row[3], row[4], None, row[5]))
        if len(rows) == 1:
            return rows[0]
        return None

    def get_entry_by_headword(self, headword, exact_headword=False):
        if exact_headword:
            exact_row = self._get_exact_headword(headword)
            if exact_row is not None:
                return exact_row
        exact = remove_accents(headword)
        search_lower = exact.lower()
        conn = self._get_connection()
        cursor = conn.cursor()

        matches = OrderedDict()

        for where_clause in ("dictionary.normalized_headword = ?", "dictionary.normalized_plain_headword = ?"):
            cursor.execute(
                _ENTRY_SELECT_SQL + "WHERE " + where_clause,
                (search_lower,),
            )
            for row in cursor.fetchall():
                matches.setdefault(
                    (row[0], row[1]),
                    (row[0], row[1], row[2], row[3], row[4], None, row[5]),
                )

        for where_clause, pack_plain in (
                ("sub_headwords.normalized_headword = ?", False),
                ("sub_headwords.normalized_plain_headword = ?", True)):
            cursor.execute(
                _SUB_MATCH_SELECT_SQL + "WHERE " + where_clause,
                (search_lower,),
            )
            for row in cursor.fetchall():
                entry_id, main_headword, full_entry, entry_link, source_file, main_keep_acc, sub_headword, sub_keep_acc = row
                if pack_plain:
                    packed = (entry_id, sub_headword, full_entry, entry_link, source_file, None, sub_keep_acc)
                else:
                    packed = (entry_id, main_headword, full_entry, entry_link, source_file, None, main_keep_acc)
                matches.setdefault((entry_id, sub_headword), packed)

        filtered = [row for (_, matched), row in matches.items() if remove_accents(matched) == exact]
        if len(filtered) == 1:
            return filtered[0]
        return _EMPTY_ENTRY_ROW

    def get_entry_by_link(self, entry_link):
        result = self._get_entry_row("dictionary.entry_link = ?", entry_link)
        if result[0] is not None:
            return result
        cursor = self._get_connection().cursor()
        cursor.execute("""
            SELECT dictionary.id, sub_headwords.headword, entry_body.xml,
                   sub_headwords.link, dictionary.source_file, sub_headwords.keep_acc
            FROM sub_headwords
            JOIN dictionary ON sub_headwords.main_entry_id = dictionary.id
            LEFT JOIN entry_body ON entry_body.id = dictionary.id
            WHERE sub_headwords.link = ?
        """, (entry_link,))
        result = cursor.fetchone()
        if result:
            return (result[0], result[1], result[2], result[3], result[4], None, result[5])
        return _EMPTY_ENTRY_ROW

    def get_entry_by_xml_id(self, xml_id):
        if not xml_id:
            return _EMPTY_ENTRY_ROW
        result = self._get_entry_row("dictionary.hw_xml_id = ?", xml_id)
        if result[0] is not None:
            return result
        cursor = self._get_connection().cursor()
        cursor.execute("""
            SELECT dictionary.id, sub_headwords.headword, entry_body.xml,
                   dictionary.entry_link, dictionary.source_file, sub_headwords.keep_acc
            FROM sub_headwords
            JOIN dictionary ON sub_headwords.main_entry_id = dictionary.id
            LEFT JOIN entry_body ON entry_body.id = dictionary.id
            WHERE sub_headwords.hw_xml_id = ?
        """, (xml_id,))
        result = cursor.fetchone()
        if result:
            return (result[0], result[1], result[2], result[3], result[4], None, result[5])
        return _EMPTY_ENTRY_ROW

    def get_entry_sub_headword(self, entry_row_id, target):
        if not entry_row_id or not target:
            return None, None
        target_exact = remove_accents(target)
        cursor = self._get_connection().cursor()
        cursor.execute(
            "SELECT headword, hw_xml_id, keep_acc FROM sub_headwords WHERE main_entry_id = ?",
            (entry_row_id,),
        )
        exact_matches = []
        for headword, hw_xml_id, keep_acc in cursor.fetchall():
            if hw_xml_id and hw_xml_id == target:
                return headword, hw_xml_id
            if headword == target:
                return headword, hw_xml_id or headword
            if remove_accents(headword) == target_exact:
                anchor = hw_xml_id or (headword if keep_acc else remove_accents(headword))
                exact_matches.append((headword, anchor))
        if len(exact_matches) == 1:
            return exact_matches[0]
        return None, None

    def get_full_entry(self, entry_id):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT xml FROM entry_body WHERE id = ?", (entry_id,))
        row = cursor.fetchone()
        return row[0] if row else None

    def get_entry_by_id(self, entry_id):
        return self._get_entry_row("dictionary.id = ?", entry_id)

    def fetch_link_target_rows(self):
        cursor = self._get_connection().cursor()
        cursor.execute("SELECT id, headword, entry_link, hw_xml_id FROM dictionary")
        dict_rows = cursor.fetchall()
        cursor.execute(
            "SELECT main_entry_id, headword, link, hw_xml_id FROM sub_headwords")
        sub_rows = cursor.fetchall()
        return dict_rows, sub_rows

    def materialize_result(self, result):
        if result is None or result[2] is not None:
            return result
        full_entry = self.get_full_entry(result[0])
        if full_entry is None:
            return None
        return (result[0], result[1], full_entry, result[3], result[4], result[5], result[6])