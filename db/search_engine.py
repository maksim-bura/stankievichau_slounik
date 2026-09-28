import sqlite3
import xml.etree.ElementTree as ElementTree
from collections import OrderedDict

from utils.text_utils import remove_accents, alphabet_sort_key
from utils.content_rules import index_text
from utils.search_regex import compile_search_regex
from utils.constants import SOURCES_PSEUDO_HEADWORD
from format.highlight_formatter import HighlightFormatter


_PARSED_CACHE_MAX_SIZE = 512
_PREVIEW_CACHE_MAX_SIZE = 2048
_TRIGRAM_MIN_SPAN = 3

_HEADWORD_ROWS_SQL = """
    SELECT id, headword, NULL AS full_entry, entry_link, source_file, sort_headword, normalized_headword FROM dictionary
    {dictionary_where}
    UNION
    SELECT dictionary.id, sub_headwords.headword, NULL AS full_entry, dictionary.entry_link, dictionary.source_file, sub_headwords.sort_headword, sub_headwords.normalized_headword
    FROM sub_headwords
    JOIN dictionary ON sub_headwords.main_entry_id = dictionary.id
    {sub_headwords_where}
"""

_ENTRY_ROWS_SQL = """
    SELECT id, headword, full_entry, entry_link, source_file FROM dictionary
    WHERE id IN ({placeholders})
    UNION
    SELECT dictionary.id, sub_headwords.headword, dictionary.full_entry, dictionary.entry_link, dictionary.source_file
    FROM sub_headwords
    JOIN dictionary ON sub_headwords.main_entry_id = dictionary.id
    WHERE dictionary.id IN ({placeholders})
"""


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

    def search_headwords(self, text):
        return self.search(text, search_in_headwords=True, search_in_translations=False, search_in_examples=False)

    def _search_headwords(self, text):
        conn = self._get_connection()
        cursor = conn.cursor()

        clean_text = remove_accents(text.strip())

        if clean_text == "":
            cursor.execute(_HEADWORD_ROWS_SQL.format(
                dictionary_where='', sub_headwords_where=''))
            unique = cursor.fetchall()
            unique.sort(key=lambda x: alphabet_sort_key(x[5] or x[1]))
            return [(r[0], r[1], r[2], r[3], r[4]) + (None,) for r in unique if r[1] != SOURCES_PSEUDO_HEADWORD]

        pattern = compile_search_regex(clean_text, exact_words=text.endswith(' '))

        dict_ids, sub_ids = self._candidate_headword_ids(clean_text)
        if dict_ids or sub_ids:
            rows = []
            if dict_ids:
                placeholders = ','.join(['?'] * len(dict_ids))
                cursor.execute(f"""
                    SELECT id, headword, NULL AS full_entry, entry_link, source_file, sort_headword, normalized_headword
                    FROM dictionary WHERE id IN ({placeholders})
                """, dict_ids)
                rows.extend(cursor.fetchall())
            if sub_ids:
                placeholders = ','.join(['?'] * len(sub_ids))
                cursor.execute(f"""
                    SELECT dictionary.id, sub_headwords.headword, NULL AS full_entry, dictionary.entry_link,
                           dictionary.source_file, sub_headwords.sort_headword, sub_headwords.normalized_headword
                    FROM sub_headwords
                    JOIN dictionary ON sub_headwords.main_entry_id = dictionary.id
                    WHERE sub_headwords.id IN ({placeholders})
                """, sub_ids)
                rows.extend(cursor.fetchall())
            unique = [r for r in rows if pattern.search(r[6])]
            unique.sort(key=lambda x: alphabet_sort_key(x[5] or x[1]))
            return [(r[0], r[1], r[2], r[3], r[4]) + (None,) for r in unique]

        sql_pattern = self._like_pattern(clean_text.lower(), collapse_spaces=True)

        cursor.execute(_HEADWORD_ROWS_SQL.format(
            dictionary_where='WHERE normalized_headword LIKE ?',
            sub_headwords_where='WHERE sub_headwords.normalized_headword LIKE ?',
        ), (sql_pattern, sql_pattern))
        unique = cursor.fetchall()

        unique = [r for r in unique if pattern.search(r[6])]
        unique.sort(key=lambda x: alphabet_sort_key(x[5] or x[1]))
        return [(r[0], r[1], r[2], r[3], r[4]) + (None,) for r in unique]

    def _candidate_headword_ids(self, clean_text):
        span = self._alphanumeric_span(clean_text)
        if len(span) < _TRIGRAM_MIN_SPAN:
            return [], []
        try:
            cursor = self._get_connection().cursor()
            cursor.execute(
                "SELECT dict_id, sub_id FROM headword_fts WHERE headword_fts MATCH ?",
                (f'"{span}"',),
            )
            dict_ids = set()
            sub_ids = set()
            for dict_id, sub_id in cursor.fetchall():
                if dict_id is not None:
                    dict_ids.add(int(dict_id))
                if sub_id is not None:
                    sub_ids.add(int(sub_id))
            return list(dict_ids), list(sub_ids)
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
        pattern = compile_search_regex(clean, exact_words=text.endswith(' '))

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
            if entry_id not in previews_by_entry:
                cache_key = (entry_id, headword, tag, pattern.pattern)
                cached = self._preview_cache.get(cache_key)
                if cached is not None:
                    self._preview_cache.move_to_end(cache_key)
                    previews_by_entry[entry_id] = cached
                else:
                    root = self.get_parsed_entry(entry_id, full_entry)
                    previews = self._highlight_formatter.find_content_matches(root, headword, tag, pattern)
                    self._preview_cache[cache_key] = previews
                    while len(self._preview_cache) > _PREVIEW_CACHE_MAX_SIZE:
                        self._preview_cache.popitem(last=False)
                    previews_by_entry[entry_id] = previews
            results[i] = result[:5] + (previews_by_entry[entry_id],)

    def apply_highlight(self, formatted_html, pattern, normalize=True, exclude_classes=None):
        return self._highlight_formatter.apply_highlight(
            formatted_html, pattern,
            normalize=normalize, exclude_classes=exclude_classes,
        )

    def _get_entry_row(self, where_clause, param):
        cursor = self._get_connection().cursor()
        cursor.execute(
            "SELECT id, headword, full_entry, entry_link, source_file "
            "FROM dictionary WHERE " + where_clause,
            (param,),
        )
        result = cursor.fetchone()
        return result + (None,) if result else None

    def get_entry_by_headword(self, headword):
        search_headword = remove_accents(headword).lower()
        result = self._get_entry_row("normalized_headword = ?", search_headword)
        if result:
            return result
        result = self._get_entry_row("normalized_plain_headword = ?", search_headword)
        if result:
            return result
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT dictionary.id, sub_headwords.headword, dictionary.entry_link, dictionary.source_file
            FROM sub_headwords
            JOIN dictionary ON sub_headwords.main_entry_id = dictionary.id
            WHERE sub_headwords.normalized_headword = ?
        """, (search_headword,))
        result = cursor.fetchone()
        if result:
            return self.get_entry_by_id(result[0])
        cursor.execute("""
            SELECT dictionary.id, sub_headwords.headword, dictionary.entry_link, dictionary.source_file
            FROM sub_headwords
            JOIN dictionary ON sub_headwords.main_entry_id = dictionary.id
            WHERE sub_headwords.normalized_plain_headword = ?
        """, (search_headword,))
        result = cursor.fetchone()
        if result:
            full_row = self.get_entry_by_id(result[0])
            if full_row:
                return (full_row[0], result[1], full_row[2], full_row[3], full_row[4], None)
        return None, None, None, None, None, None

    def get_entry_by_link(self, entry_link):
        return self._get_entry_row("entry_link = ?", entry_link)

    def get_full_entry(self, entry_id):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT full_entry FROM dictionary WHERE id = ?", (entry_id,))
        row = cursor.fetchone()
        return row[0] if row else None

    def get_entry_by_id(self, entry_id):
        return self._get_entry_row("id = ?", entry_id)

    def materialize_result(self, result):
        if result is None or result[2] is not None:
            return result
        full_entry = self.get_full_entry(result[0])
        if full_entry is None:
            return None
        return (result[0], result[1], full_entry, result[3], result[4], result[5])