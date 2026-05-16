import sqlite3
import xml.etree.ElementTree as ElementTree
import os
from utils.accent_utils import remove_accents


def parse_with_error_handling(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    return ElementTree.fromstring(content)


def get_paths():
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return {
        'dictionary_xml': os.path.join(base, 'data', 'dictionary.xml'),
        'sources_xml': os.path.join(base, 'data', 'sources.xml'),
        'database': os.path.join(base, 'build', 'dictionary.db'),
        'build_dir': os.path.join(base, 'build'),
    }


def needs_rebuild():
    paths = get_paths()
    db_path = paths['database']
    if not os.path.exists(db_path):
        return True
    db_mtime = os.path.getmtime(db_path)
    for key in ('dictionary_xml', 'sources_xml'):
        xml_path = paths[key]
        if os.path.exists(xml_path) and os.path.getmtime(xml_path) > db_mtime:
            return True
    return False


def build_database():
    paths = get_paths()
    os.makedirs(paths['build_dir'], exist_ok=True)

    root_dict = parse_with_error_handling(paths['dictionary_xml'])
    entries_dict = root_dict.findall("entry")

    tree_sources = ElementTree.parse(paths['sources_xml'])
    root_sources = tree_sources.getroot()
    entries_sources = root_sources.findall("entry")

    all_entries = entries_dict + entries_sources

    db_path = paths['database']
    if os.path.exists(db_path):
        os.remove(db_path)

    connection = sqlite3.connect(db_path)
    cursor = connection.cursor()

    cursor.execute("""
        CREATE TABLE dictionary (
            id INTEGER PRIMARY KEY,
            headword TEXT,
            normalized_headword TEXT,
            full_entry TEXT,
            entry_link TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE sub_headwords (
            id INTEGER PRIMARY KEY,
            headword TEXT,
            normalized_headword TEXT,
            main_entry_id INTEGER
        )
    """)

    for entry in all_entries:
        headword_element = entry.find("hw")
        if headword_element is None:
            continue

        headword = ''.join(headword_element.itertext()).strip()

        if not headword:
            continue

        normalized_headword = remove_accents(headword)
        entry_string = ElementTree.tostring(entry, encoding="unicode")
        entry_link = entry.get('link')

        cursor.execute(
            "INSERT INTO dictionary (headword, normalized_headword, full_entry, entry_link) VALUES (?, ?, ?, ?)",
            (headword, normalized_headword, entry_string, entry_link)
        )

        main_entry_id = cursor.lastrowid

        all_headwords = entry.findall(".//hw")
        for sub_headword_element in all_headwords[1:]:
            if sub_headword_element.text:
                sub_normalized = remove_accents(sub_headword_element.text)
                cursor.execute(
                    "INSERT INTO sub_headwords (headword, normalized_headword, main_entry_id) VALUES (?, ?, ?)",
                    (sub_headword_element.text, sub_normalized, main_entry_id)
                )

    connection.commit()
    connection.close()


if __name__ == "__main__":
    build_database()
