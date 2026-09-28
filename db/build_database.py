import sqlite3
import xml.etree.ElementTree as ElementTree
import os
import stat
from utils.text_utils import remove_accents
from utils.content_rules import content_text, index_text, hw_text_excluding_n


_DICTIONARY_INSERT_SQL = (
    "INSERT INTO dictionary (id, headword, sort_headword, normalized_headword, "
    "normalized_plain_headword, full_entry, entry_link, source_file) "
    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
)
_SUB_HEADWORD_INSERT_SQL = (
    "INSERT INTO sub_headwords (headword, sort_headword, normalized_headword, "
    "normalized_plain_headword, main_entry_id) VALUES (?, ?, ?, ?, ?)"
)
_CONTENT_INDEX_INSERT_SQL = (
    "INSERT INTO content_index (entry_id, tag_type, searchable_text) VALUES (?, ?, ?)"
)
_BATCH_SIZE = 10000

_SQLITE_SYNCHRONOUS_OFF = "PRAGMA synchronous = OFF"
_SQLITE_CACHE_SIZE_KIB = "PRAGMA cache_size = -20000"


def parse_xml_file(file_path):
    return ElementTree.parse(file_path).getroot()


def get_paths():
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return {
        'dictionary_dir': os.path.join(base, 'data', 'dictionary'),
        'sources_xml': os.path.join(base, 'data', 'sources.xml'),
        'database': os.path.join(base, 'build', 'dictionary.db'),
        'build_dir': os.path.join(base, 'build'),
    }


def get_source_path(source_file):
    paths = get_paths()
    if source_file == 'sources.xml':
        return paths['sources_xml']
    return os.path.join(paths['dictionary_dir'], source_file)


def _scan_source_files():
    paths = get_paths()
    found = []
    dict_dir = paths['dictionary_dir']
    try:
        with os.scandir(dict_dir) as iterator:
            for entry in iterator:
                if not entry.name.endswith('.xml'):
                    continue
                try:
                    is_file = stat.S_ISREG(entry.stat().st_mode)
                except OSError:
                    continue
                if is_file:
                    found.append((entry.name, entry.stat().st_mtime))
    except OSError:
        return []
    found.sort(key=lambda item: item[0])
    return found


def get_source_names():
    return [name for name, _ in _scan_source_files()]


def stale_source_files():
    paths = get_paths()
    db_path = paths['database']
    if not os.path.exists(db_path):
        return get_source_names() + ['sources.xml']
    db_mtime = os.path.getmtime(db_path)
    stale = []
    if os.path.exists(paths['sources_xml']) and os.path.getmtime(paths['sources_xml']) > db_mtime:
        stale.append('sources.xml')
    for name, mtime in _scan_source_files():
        if mtime > db_mtime:
            stale.append(name)
    return stale


def build_database(file_names=None):
    paths = get_paths()
    os.makedirs(paths['build_dir'], exist_ok=True)

    db_path = paths['database']

    rebuild_all = file_names is None or not os.path.exists(db_path)
    if rebuild_all:
        file_names = get_source_names() + ['sources.xml']

    connection = sqlite3.connect(db_path)
    cursor = connection.cursor()
    cursor.execute(_SQLITE_SYNCHRONOUS_OFF)
    cursor.execute(_SQLITE_CACHE_SIZE_KIB)

    if rebuild_all:

        cursor.execute("DROP TABLE IF EXISTS dictionary")
        cursor.execute("DROP TABLE IF EXISTS sub_headwords")
        cursor.execute("DROP TABLE IF EXISTS content_index")
        cursor.execute("DROP TABLE IF EXISTS content_fts_t")
        cursor.execute("DROP TABLE IF EXISTS content_fts_ex")

        cursor.execute("""
            CREATE TABLE dictionary (
                id INTEGER PRIMARY KEY,
                headword TEXT,
                sort_headword TEXT,
                normalized_headword TEXT,
                normalized_plain_headword TEXT,
                full_entry TEXT,
                entry_link TEXT,
                source_file TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE sub_headwords (
                id INTEGER PRIMARY KEY,
                headword TEXT,
                sort_headword TEXT,
                normalized_headword TEXT,
                normalized_plain_headword TEXT,
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
        cursor.execute("CREATE INDEX idx_dictionary_normalized ON dictionary(normalized_headword)")
        cursor.execute("CREATE INDEX idx_dictionary_plain ON dictionary(normalized_plain_headword)")
        cursor.execute("CREATE INDEX idx_sub_normalized ON sub_headwords(normalized_headword)")
        cursor.execute("CREATE INDEX idx_sub_plain ON sub_headwords(normalized_plain_headword)")

    dict_rows = []
    sub_rows = []
    content_rows = []

    def flush():
        if dict_rows:
            cursor.executemany(_DICTIONARY_INSERT_SQL, dict_rows)
            dict_rows.clear()
        if sub_rows:
            cursor.executemany(_SUB_HEADWORD_INSERT_SQL, sub_rows)
            sub_rows.clear()
        if content_rows:
            cursor.executemany(_CONTENT_INDEX_INSERT_SQL, content_rows)
            content_rows.clear()

    for fname in file_names:
        cursor.execute(
            "DELETE FROM sub_headwords WHERE main_entry_id IN (SELECT id FROM dictionary WHERE source_file = ?)",
            (fname,),
        )
        cursor.execute(
            "DELETE FROM content_index WHERE entry_id IN (SELECT id FROM dictionary WHERE source_file = ?)",
            (fname,),
        )
        cursor.execute("DELETE FROM dictionary WHERE source_file = ?", (fname,))

        root = parse_xml_file(get_source_path(fname))
        next_id = cursor.execute("SELECT IFNULL(MAX(id), 0) FROM dictionary").fetchone()[0]
        for entry in root.findall("entry"):
            next_id += 1
            rows = insert_entry(entry, fname, next_id)
            if rows is None:
                continue
            dict_rows.append(rows[0])
            sub_rows.extend(rows[1])
            content_rows.extend(rows[2])
            if len(dict_rows) >= _BATCH_SIZE:
                flush()
        flush()

    cursor.execute("CREATE VIRTUAL TABLE IF NOT EXISTS content_fts_t USING fts5(searchable_text, tokenize = \"trigram\")")
    cursor.execute("CREATE VIRTUAL TABLE IF NOT EXISTS content_fts_ex USING fts5(searchable_text, tokenize = \"trigram\")")
    cursor.execute("DELETE FROM content_fts_t")
    cursor.execute("DELETE FROM content_fts_ex")
    cursor.execute("INSERT INTO content_fts_t(rowid, searchable_text) SELECT id, searchable_text FROM content_index WHERE tag_type = 't'")
    cursor.execute("INSERT INTO content_fts_ex(rowid, searchable_text) SELECT id, searchable_text FROM content_index WHERE tag_type = 'ex'")
    cursor.execute("CREATE VIRTUAL TABLE IF NOT EXISTS headword_fts USING fts5(word, dict_id UNINDEXED, sub_id UNINDEXED, tokenize = \"trigram\")")
    cursor.execute("DELETE FROM headword_fts")
    cursor.execute("INSERT INTO headword_fts(word, dict_id, sub_id) SELECT normalized_headword, id, NULL FROM dictionary")
    cursor.execute("INSERT INTO headword_fts(word, dict_id, sub_id) SELECT normalized_headword, NULL, id FROM sub_headwords")

    connection.commit()
    connection.close()


def insert_entry(entry, source_file, main_entry_id):
    headword_elements = []
    t_elements = []
    ex_elements = []
    for element in entry.iter():
        if element.tag == 'hw':
            headword_elements.append(element)
        elif element.tag == 't':
            t_elements.append(element)
        elif element.tag == 'ex':
            ex_elements.append(element)

    headword_element = next(
        (h for h in headword_elements if h.get('excl') is None),
        headword_elements[0] if headword_elements else None
    )
    if headword_element is None:
        return None

    headword = ''.join(headword_element.itertext()).strip()
    if not headword:
        return None

    sort_headword = hw_text_excluding_n(headword_element).strip() or headword
    normalized_headword = remove_accents(sort_headword).lower()
    entry_string = ElementTree.tostring(entry, encoding="unicode")
    entry_link = entry.get('link')

    dict_row = (
        main_entry_id, headword, sort_headword, normalized_headword,
        remove_accents(headword).lower(), entry_string, entry_link, source_file
    )

    sub_rows = []
    seen_sub_headwords = set()
    for sub_headword_element in headword_elements:
        if sub_headword_element is headword_element:
            continue
        if sub_headword_element.get('excl') is not None:
            continue
        sub_text = ''.join(sub_headword_element.itertext()).strip()
        if sub_text:
            sub_sort = hw_text_excluding_n(sub_headword_element).strip() or sub_text
            sub_normalized = remove_accents(sub_sort).lower()
            if sub_normalized in seen_sub_headwords:
                continue
            seen_sub_headwords.add(sub_normalized)
            sub_rows.append(
                (sub_text, sub_sort, sub_normalized, remove_accents(sub_text).lower(), main_entry_id)
            )

    content_rows = []
    for t_elem in t_elements:
        text = content_text(t_elem, 't')
        if text.strip():
            content_rows.append((main_entry_id, 't', index_text(text, 't')))

    for ex_elem in ex_elements:
        text = content_text(ex_elem, 'ex')
        if text.strip():
            content_rows.append((main_entry_id, 'ex', index_text(text, 'ex')))

    return dict_row, sub_rows, content_rows