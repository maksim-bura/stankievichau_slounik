import sqlite3
import xml.etree.ElementTree as ElementTree
import os
from utils.accent_utils import remove_accents, normalize_jo, get_text_excluding_src


def parse_with_error_handling(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    return ElementTree.fromstring(content)


def get_paths():
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return {
        'dictionary_dir': os.path.join(base, 'data', 'dictionary'),
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
    if os.path.exists(paths['sources_xml']) and os.path.getmtime(paths['sources_xml']) > db_mtime:
        return True
    dict_dir = paths['dictionary_dir']
    if os.path.isdir(dict_dir):
        for fname in os.listdir(dict_dir):
            fpath = os.path.join(dict_dir, fname)
            if os.path.isfile(fpath) and os.path.getmtime(fpath) > db_mtime:
                return True
    return False


def build_database():
    paths = get_paths()
    os.makedirs(paths['build_dir'], exist_ok=True)

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
            entry_link TEXT,
            source_file TEXT
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

    cursor.execute("""
        CREATE TABLE content_index (
            id INTEGER PRIMARY KEY,
            entry_id INTEGER,
            tag_type TEXT,
            searchable_text TEXT
        )
    """)

    cursor.execute("CREATE INDEX idx_content_search ON content_index(tag_type, searchable_text)")
    cursor.execute("CREATE INDEX idx_content_entry_id ON content_index(entry_id)")

    def _insert_entry(entry, source_file):
        headword_element = entry.find("hw")
        if headword_element is None:
            return

        headword = ''.join(headword_element.itertext()).strip()
        if not headword:
            return

        normalized_headword = remove_accents(headword).lower()
        entry_string = ElementTree.tostring(entry, encoding="unicode")
        entry_link = entry.get('link')

        cursor.execute(
            "INSERT INTO dictionary (headword, normalized_headword, full_entry, entry_link, source_file) VALUES (?, ?, ?, ?, ?)",
            (headword, normalized_headword, entry_string, entry_link, source_file)
        )

        main_entry_id = cursor.lastrowid

        all_headwords = entry.findall(".//hw")
        for sub_headword_element in all_headwords[1:]:
            if sub_headword_element.text:
                sub_normalized = remove_accents(sub_headword_element.text).lower()
                cursor.execute(
                    "INSERT INTO sub_headwords (headword, normalized_headword, main_entry_id) VALUES (?, ?, ?)",
                    (sub_headword_element.text, sub_normalized, main_entry_id)
                )

        for t_elem in entry.iter('t'):
            text = get_text_excluding_src(t_elem, extra_exclude={'see'}, skip_attrs={'lang': 'vl', 'excl': None})
            if text.strip():
                index_text = normalize_jo(remove_accents(text.lower()))
                cursor.execute(
                    "INSERT INTO content_index (entry_id, tag_type, searchable_text) VALUES (?, ?, ?)",
                    (main_entry_id, 't', index_text)
                )

        for ex_elem in entry.iter('ex'):
            text = get_text_excluding_src(ex_elem, skip_attrs={'lang': 'ru'})
            if text.strip():
                index_text = remove_accents(text.lower())
                cursor.execute(
                    "INSERT INTO content_index (entry_id, tag_type, searchable_text) VALUES (?, ?, ?)",
                    (main_entry_id, 'ex', index_text)
                )

    dict_dir = paths['dictionary_dir']
    for fname in sorted(os.listdir(dict_dir)):
        fpath = os.path.join(dict_dir, fname)
        if not os.path.isfile(fpath) or not (fname.endswith('.xml') or fname.endswith('.txt')):
            continue
        root = parse_with_error_handling(fpath)
        for entry in root.findall("entry"):
            _insert_entry(entry, fname)

    tree_sources = ElementTree.parse(paths['sources_xml'])
    root_sources = tree_sources.getroot()
    for entry in root_sources.findall("entry"):
        _insert_entry(entry, 'sources.xml')

    connection.commit()
    connection.close()


if __name__ == "__main__":
    build_database()
