import sqlite3
from utils.accent_utils import remove_accents


class SearchEngine:
    def __init__(self, database_path):
        self.database_path = database_path

    def search(self, text):
        connection = sqlite3.connect(self.database_path)
        cursor = connection.cursor()

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

        connection.close()

        results_dict = {}
        for result in main_results + sub_results:
            key = (result[0], result[1])
            if key not in results_dict:
                results_dict[key] = result

        unique_results = list(results_dict.values())
        unique_results.sort(key=lambda x: x[1])
        return unique_results

    def get_entry(self, entry_id):
        connection = sqlite3.connect(self.database_path)
        cursor = connection.cursor()
        cursor.execute("SELECT full_entry FROM dictionary WHERE id = ?", (entry_id,))
        result = cursor.fetchone()
        connection.close()
        return result[0] if result else None

    def get_entry_by_headword(self, headword):
        connection = sqlite3.connect(self.database_path)
        cursor = connection.cursor()
        search_headword = remove_accents(headword)
        cursor.execute("""
            SELECT id, headword, full_entry, entry_link
            FROM dictionary
            WHERE normalized_headword = ?
        """, (search_headword,))
        result = cursor.fetchone()
        print(f"DEBUG get_entry_by_headword: headword={headword}, result={result}")
        connection.close()
        if result:
            return result[0], result[1], result[2], result[3]
        return None, None, None, None

    def get_entry_by_id(self, entry_link):
        connection = sqlite3.connect(self.database_path)
        cursor = connection.cursor()
        cursor.execute("""
            SELECT id, headword, full_entry, entry_link
            FROM dictionary
            WHERE entry_link = ?
        """, (entry_link,))
        result = cursor.fetchone()
        connection.close()
        return result