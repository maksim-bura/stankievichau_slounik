import sqlite3
import xml.etree.ElementTree as ElementTree
from utils.accent_utils import remove_accents


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

    def search(self, text):
        conn = self._get_connection()
        cursor = conn.cursor()

        search_text = remove_accents(text.strip())

        if search_text == "":
            cursor.execute("""
                SELECT id, headword, full_entry, entry_link
                FROM dictionary
                ORDER BY normalized_headword
            """)
            main_results = cursor.fetchall()

            cursor.execute("""
                SELECT dictionary.id, sub_headwords.headword, dictionary.full_entry, dictionary.entry_link
                FROM sub_headwords
                JOIN dictionary ON sub_headwords.main_entry_id = dictionary.id
                ORDER BY sub_headwords.normalized_headword
            """)
            sub_results = cursor.fetchall()

            combined = main_results + sub_results
            unique = list({(result[0], result[1]): result for result in combined}.values())
            unique.sort(key=lambda x: x[1])
            return [r for r in unique if r[1] != "!SOURCES"]
        else:
            if '*' in search_text:
                pattern = search_text.replace('*', '%')
            else:
                pattern = f"{search_text}%"

            cursor.execute("""
                SELECT id, headword, full_entry, entry_link
                FROM dictionary
                WHERE normalized_headword LIKE ?
                ORDER BY normalized_headword
            """, (pattern,))
            main_results = cursor.fetchall()

            cursor.execute("""
                SELECT dictionary.id, sub_headwords.headword, dictionary.full_entry, dictionary.entry_link
                FROM sub_headwords
                JOIN dictionary ON sub_headwords.main_entry_id = dictionary.id
                WHERE sub_headwords.normalized_headword LIKE ?
                ORDER BY sub_headwords.normalized_headword
            """, (pattern,))
            sub_results = cursor.fetchall()

            combined = main_results + sub_results
            unique = list({(result[0], result[1]): result for result in combined}.values())
            unique.sort(key=lambda x: x[1])
            return unique

    def get_entry_by_headword(self, headword):
        conn = self._get_connection()
        cursor = conn.cursor()
        search_headword = remove_accents(headword)
        cursor.execute("""
            SELECT id, headword, full_entry, entry_link
            FROM dictionary
            WHERE normalized_headword = ?
        """, (search_headword,))
        result = cursor.fetchone()
        if result:
            return result[0], result[1], result[2], result[3]
        return None, None, None, None

    def get_entry_by_id(self, entry_link):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, headword, full_entry, entry_link
            FROM dictionary
            WHERE entry_link = ?
        """, (entry_link,))
        result = cursor.fetchone()
        return result
