import sqlite3
import xml.etree.ElementTree as ElementTree
import os
from utils.accent_utils import remove_accents

def parse_with_error_handling(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    return ElementTree.fromstring(content)

base_dir = os.path.dirname(os.path.abspath(__file__))
build_dir = os.path.join(os.path.dirname(base_dir), 'build')
os.makedirs(build_dir, exist_ok=True)

dictionary_path = os.path.join(base_dir, 'dictionary.xml')
sources_path = os.path.join(base_dir, 'sources.xml')

root_dict = parse_with_error_handling(dictionary_path)
entries_dict = root_dict.findall("entry")

tree_sources = ElementTree.parse(sources_path)
root_sources = tree_sources.getroot()
entries_sources = root_sources.findall("entry")

all_entries = entries_dict + entries_sources

database_path = os.path.join(build_dir, 'dictionary.db')
if os.path.exists(database_path):
    os.remove(database_path)

connection = sqlite3.connect(database_path)
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