import sqlite3
import xml.etree.ElementTree as ElementTree
import os
import stat
from dictionary_app.utils.remove_accents import remove_accents
from dictionary_app.utils.sort_keys import alphabet_sort_key, encode_order_key, entry_id_sort_key
from dictionary_app.utils.extract_content_text import content_text, index_text, hw_text_excluding_n
from dictionary_app.utils.xml_schema import ATTR_ID, ATTR_EXCL, ATTR_KEEP_ACC


_DICTIONARY_INSERT_SQL = (
    "INSERT INTO dictionary (id, headword, sort_headword, normalized_headword, "
    "normalized_plain_headword, collation_key, entry_link, hw_xml_id, source_file, keep_acc) "
    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
)
_ENTRY_BODY_INSERT_SQL = "INSERT INTO entry_body (id, xml) VALUES (?, ?)"
_SUB_HEADWORD_INSERT_SQL = (
    "INSERT INTO sub_headwords (headword, sort_headword, normalized_headword, "
    "normalized_plain_headword, collation_key, main_entry_id, link, hw_xml_id, keep_acc) "
    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
)
_CONTENT_INDEX_INSERT_SQL = (
    "INSERT INTO content_index (entry_id, tag_type, searchable_text) VALUES (?, ?, ?)"
)
_BATCH_SIZE = 10000

_SQLITE_SYNCHRONOUS_OFF = "PRAGMA synchronous = OFF"
_SQLITE_CACHE_SIZE_KIB = "PRAGMA cache_size = -20000"
_SQLITE_CACHE_SIZE_VALUE = -20000

_SCHEMA_VERSION_KEY = 'schema_version'
_SCHEMA_VERSION = 5

_SOURCES_XML = 'sources.xml'

_FTS_HEADWORD = 'headword_fts'
_FTS_SUB_HEADWORD = 'sub_headword_fts'
_FTS_CONTENT_T = 'content_fts_t'
_FTS_CONTENT_EX = 'content_fts_ex'
_FTS_TABLES = (_FTS_HEADWORD, _FTS_SUB_HEADWORD, _FTS_CONTENT_T, _FTS_CONTENT_EX)
_BASE_TABLES = ('dictionary', 'entry_body', 'sub_headwords', 'content_index')


def _collation_key(sort_headword, entry_link, hw_xml_id):
    return encode_order_key(
        *alphabet_sort_key(sort_headword),
        entry_id_sort_key(entry_link) or entry_id_sort_key(hw_xml_id),
    )


def _parse_xml_file(file_path):
    return ElementTree.parse(file_path).getroot()


def get_paths():
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return {
        'dictionary_dir': os.path.join(base, 'data', 'dictionary'),
        'sources_xml': os.path.join(base, 'data', _SOURCES_XML),
        'database': os.path.join(base, 'build', 'dictionary.db'),
        'build_dir': os.path.join(base, 'build'),
    }


def get_source_path(source_file):
    paths = get_paths()
    if source_file == _SOURCES_XML:
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
        return get_source_names() + [_SOURCES_XML]
    db_mtime = os.path.getmtime(db_path)
    stale = []
    if os.path.exists(paths['sources_xml']) and os.path.getmtime(paths['sources_xml']) > db_mtime:
        stale.append(_SOURCES_XML)
    for name, mtime in _scan_source_files():
        if mtime > db_mtime:
            stale.append(name)
    return stale


def _schema_is_current(cursor):
    tables = {row[0] for row in cursor.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    if not {'dictionary', 'sub_headwords', 'entry_body', 'schema_meta'}.issubset(tables):
        return False
    columns = {row[1] for row in cursor.execute("PRAGMA table_info(sub_headwords)")}
    if not {'link', 'hw_xml_id', 'keep_acc', 'collation_key'}.issubset(columns):
        return False
    dict_columns = {row[1] for row in cursor.execute("PRAGMA table_info(dictionary)")}
    if not {'hw_xml_id', 'keep_acc', 'collation_key'}.issubset(dict_columns):
        return False
    row = cursor.execute("SELECT value FROM schema_meta WHERE key = ?", (_SCHEMA_VERSION_KEY,)).fetchone()
    return bool(row) and row[0] == str(_SCHEMA_VERSION)


def database_schema_is_current(db_path):
    if not os.path.exists(db_path):
        return False
    try:
        connection = sqlite3.connect(db_path)
    except sqlite3.Error:
        return False
    try:
        return _schema_is_current(connection.cursor())
    except sqlite3.Error:
        return False
    finally:
        connection.close()


def _delete_rows(cursor, column, value):
    scope = f"d.{column} = ?"
    cursor.execute(
        f"DELETE FROM {_FTS_HEADWORD} WHERE rowid IN "
        f"(SELECT d.id FROM dictionary d WHERE {scope})", (value,))
    cursor.execute(
        f"DELETE FROM {_FTS_SUB_HEADWORD} WHERE rowid IN "
        "(SELECT s.id FROM sub_headwords s JOIN dictionary d ON s.main_entry_id = d.id "
        f"WHERE {scope})", (value,))
    for fts_table in (_FTS_CONTENT_T, _FTS_CONTENT_EX):
        cursor.execute(
            f"DELETE FROM {fts_table} WHERE rowid IN "
            "(SELECT c.id FROM content_index c JOIN dictionary d ON c.entry_id = d.id "
            f"WHERE {scope})", (value,))
    for table, join_column in (
        ('entry_body', 'id'),
        ('content_index', 'entry_id'),
        ('sub_headwords', 'main_entry_id'),
    ):
        cursor.execute(
            f"DELETE FROM {table} WHERE {join_column} IN "
            f"(SELECT d.id FROM dictionary d WHERE {scope})", (value,))
    cursor.execute(f"DELETE FROM dictionary WHERE {column} = ?", (value,))


def _populate_fts(cursor, column, value):
    scope = f"d.{column} = ?"
    cursor.execute(
        f"INSERT INTO {_FTS_HEADWORD}(rowid, word) "
        f"SELECT d.id, d.normalized_headword FROM dictionary d WHERE {scope}", (value,))
    cursor.execute(
        f"INSERT INTO {_FTS_SUB_HEADWORD}(rowid, word) "
        "SELECT s.id, s.normalized_headword FROM sub_headwords s "
        f"JOIN dictionary d ON s.main_entry_id = d.id WHERE {scope}", (value,))
    for fts_table, tag_type in ((_FTS_CONTENT_T, 't'), (_FTS_CONTENT_EX, 'ex')):
        cursor.execute(
            f"INSERT INTO {fts_table}(rowid, searchable_text) "
            "SELECT c.id, c.searchable_text FROM content_index c "
            "JOIN dictionary d ON c.entry_id = d.id "
            f"WHERE {scope} AND c.tag_type = '{tag_type}'", (value,))


def build_database(file_names=None):
    paths = get_paths()
    os.makedirs(paths['build_dir'], exist_ok=True)

    db_path = paths['database']

    rebuild_all = file_names is None or not os.path.exists(db_path)
    if rebuild_all:
        file_names = get_source_names() + [_SOURCES_XML]

    connection = sqlite3.connect(db_path)
    cursor = connection.cursor()
    cursor.execute(_SQLITE_SYNCHRONOUS_OFF)
    cursor.execute(f"PRAGMA cache_size = {_SQLITE_CACHE_SIZE_VALUE}")

    if not rebuild_all and not _schema_is_current(cursor):
        rebuild_all = True
        file_names = get_source_names() + [_SOURCES_XML]

    if rebuild_all:

        for table in _FTS_TABLES + _BASE_TABLES:
            cursor.execute(f"DROP TABLE IF EXISTS {table}")

        cursor.execute("""
            CREATE TABLE dictionary (
                id INTEGER PRIMARY KEY,
                headword TEXT,
                sort_headword TEXT,
                normalized_headword TEXT,
                normalized_plain_headword TEXT,
                collation_key BLOB,
                entry_link TEXT,
                hw_xml_id TEXT,
                source_file TEXT,
                keep_acc INTEGER
            )
        """)

        cursor.execute("""
            CREATE TABLE entry_body (
                id INTEGER PRIMARY KEY,
                xml TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE sub_headwords (
                id INTEGER PRIMARY KEY,
                headword TEXT,
                sort_headword TEXT,
                normalized_headword TEXT,
                normalized_plain_headword TEXT,
                collation_key BLOB,
                main_entry_id INTEGER,
                link TEXT,
                hw_xml_id TEXT,
                keep_acc INTEGER
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

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS schema_meta (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        cursor.execute(
            "INSERT OR REPLACE INTO schema_meta(key, value) VALUES (?, ?)",
            (_SCHEMA_VERSION_KEY, str(_SCHEMA_VERSION)),
        )

    cursor.execute(f"CREATE VIRTUAL TABLE IF NOT EXISTS {_FTS_HEADWORD} USING fts5(word, tokenize = \"trigram\")")
    cursor.execute(f"CREATE VIRTUAL TABLE IF NOT EXISTS {_FTS_SUB_HEADWORD} USING fts5(word, tokenize = \"trigram\")")
    cursor.execute(f"CREATE VIRTUAL TABLE IF NOT EXISTS {_FTS_CONTENT_T} USING fts5(searchable_text, tokenize = \"trigram\")")
    cursor.execute(f"CREATE VIRTUAL TABLE IF NOT EXISTS {_FTS_CONTENT_EX} USING fts5(searchable_text, tokenize = \"trigram\")")

    dict_rows = []
    body_rows = []
    sub_rows = []
    content_rows = []

    def flush():
        if dict_rows:
            cursor.executemany(_DICTIONARY_INSERT_SQL, dict_rows)
            dict_rows.clear()
        if body_rows:
            cursor.executemany(_ENTRY_BODY_INSERT_SQL, body_rows)
            body_rows.clear()
        if sub_rows:
            cursor.executemany(_SUB_HEADWORD_INSERT_SQL, sub_rows)
            sub_rows.clear()
        if content_rows:
            cursor.executemany(_CONTENT_INDEX_INSERT_SQL, content_rows)
            content_rows.clear()

    for fname in file_names:
        _delete_rows(cursor, 'source_file', fname)

        root = _parse_xml_file(get_source_path(fname))
        next_id = cursor.execute("SELECT IFNULL(MAX(id), 0) FROM dictionary").fetchone()[0]
        for entry in root.findall("entry"):
            next_id += 1
            rows = insert_entry(entry, fname, next_id)
            if rows is None:
                continue
            dict_rows.append(rows[0])
            body_rows.append(rows[1])
            sub_rows.extend(rows[2])
            content_rows.extend(rows[3])
            if len(dict_rows) >= _BATCH_SIZE:
                flush()
        flush()
        _populate_fts(cursor, 'source_file', fname)

    connection.commit()
    connection.close()


def reindex_entry(entry_id, xml_text):
    db_path = get_paths()['database']
    if not os.path.exists(db_path):
        return None
    try:
        entry = ElementTree.fromstring(xml_text)
    except ElementTree.ParseError:
        return None

    connection = sqlite3.connect(db_path)
    try:
        cursor = connection.cursor()
        cursor.execute(_SQLITE_SYNCHRONOUS_OFF)
        row = cursor.execute(
            "SELECT source_file FROM dictionary WHERE id = ?", (entry_id,)
        ).fetchone()
        if row is None:
            return None
        rows = insert_entry(entry, row[0], entry_id)
        _delete_rows(cursor, 'id', entry_id)
        if rows is not None:
            dict_row, body_row, sub_rows, content_rows = rows
            cursor.execute(_DICTIONARY_INSERT_SQL, dict_row)
            cursor.execute(_ENTRY_BODY_INSERT_SQL, body_row)
            if sub_rows:
                cursor.executemany(_SUB_HEADWORD_INSERT_SQL, sub_rows)
            if content_rows:
                cursor.executemany(_CONTENT_INDEX_INSERT_SQL, content_rows)
            _populate_fts(cursor, 'id', entry_id)
        connection.commit()
        if rows is None:
            return None
        return rows[0][1], rows[0][6], rows[0][9]
    finally:
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
        (h for h in headword_elements if h.get(ATTR_EXCL) is None),
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
    entry_xml_id = entry.get(ATTR_ID)
    main_hw_xml_id = headword_element.get(ATTR_ID)

    main_hw_keep_acc = 1 if headword_element.get(ATTR_KEEP_ACC) is not None else 0
    dict_row = (
        main_entry_id, headword, sort_headword, normalized_headword,
        remove_accents(headword).lower(),
        _collation_key(sort_headword, entry_xml_id, main_hw_xml_id),
        entry_xml_id, main_hw_xml_id, source_file, main_hw_keep_acc
    )
    body_row = (main_entry_id, entry_string)

    sub_rows = []
    seen_sub_headwords = set()
    for sub_headword_element in headword_elements:
        if sub_headword_element is headword_element:
            continue
        if sub_headword_element.get(ATTR_EXCL) is not None:
            continue
        sub_text = ''.join(sub_headword_element.itertext()).strip()
        if sub_text:
            descriptor = sub_headword_element.get(ATTR_ID)
            sub_link = entry.get(ATTR_ID)
            sub_sort = hw_text_excluding_n(sub_headword_element).strip() or sub_text
            sub_normalized = remove_accents(sub_sort).lower()
            if descriptor is not None:
                dedup_key = (sub_normalized, descriptor)
                if dedup_key in seen_sub_headwords:
                    continue
                seen_sub_headwords.add(dedup_key)
            sub_keep_acc = 1 if sub_headword_element.get(ATTR_KEEP_ACC) is not None else 0
            sub_rows.append(
                (sub_text, sub_sort, sub_normalized, remove_accents(sub_text).lower(),
                 _collation_key(sub_sort, sub_link, descriptor),
                 main_entry_id, sub_link, descriptor, sub_keep_acc)
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

    return dict_row, body_row, sub_rows, content_rows
