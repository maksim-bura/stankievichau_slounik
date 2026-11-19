import argparse
import hashlib
import json
import os
import sqlite3
import sys
import xml.etree.ElementTree as ElementTree
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = TOOLS_DIR.parent

sys.path.insert(0, str(PROJECT_ROOT))

from dictionary_app.db.build_database import get_paths
from dictionary_app.db.search_engine import SearchEngine
from dictionary_app.format.format_entry import clear_target, format_entry, set_target_subheadword
from dictionary_app.format.render_sources import build_filtered_html, normalize_anchor
from dictionary_app.utils.sort_keys import SORT_ORDER_DICTIONARY, SORT_ORDER_STANDARD
from markup_app.services.broken_link_analyzer import BrokenLinkAnalyzer
from markup_app.services.source_blocks import SourceBlocks

SNAPSHOT_VERSION = 1
DEFAULT_OUTPUT = TOOLS_DIR / 'build' / 'behavior_snapshot.json'
SEARCH_ROW_LIMIT = 80
PREVIEW_LIMIT = 40
SOURCES_SEARCH = 'а'
SOURCES_NO_MATCH = 'zzz'
SEARCH_CASES = (
    ('', 'headwords', SORT_ORDER_STANDARD),
    ('а', 'headwords', SORT_ORDER_STANDARD),
    ('а', 'headwords', SORT_ORDER_DICTIONARY),
    ('абора', 'headwords', SORT_ORDER_STANDARD),
    ('зачапіцца', 'headwords', SORT_ORDER_STANDARD),
    ('ёсьць', 'headwords', SORT_ORDER_STANDARD),
    ('ґен', 'headwords', SORT_ORDER_DICTIONARY),
    ('Халімон', 'headwords', SORT_ORDER_STANDARD),
    ('ю*', 'headwords', SORT_ORDER_STANDARD),
    ('   ', 'headwords', SORT_ORDER_STANDARD),
    ('дом', 'translations', SORT_ORDER_STANDARD),
    ('рука', 'translations', SORT_ORDER_STANDARD),
    ('чалавек', 'translations', SORT_ORDER_STANDARD),
    ('дом', 'examples', SORT_ORDER_STANDARD),
    ('рука', 'examples', SORT_ORDER_STANDARD),
    ('чалавек', 'examples', SORT_ORDER_STANDARD),
)


def parse_args():
    parser = argparse.ArgumentParser(
        description='Golden snapshot of derived dictionary/markup behavior.')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--save', nargs='?', const=str(DEFAULT_OUTPUT),
                       default=None, metavar='PATH')
    group.add_argument('--check', nargs='?', const=str(DEFAULT_OUTPUT),
                       default=None, metavar='PATH')
    parser.add_argument('--database', default=None)
    parser.add_argument('--entries', type=int, default=150,
                        help='entry HTML samples (0 = every entry)')
    parser.add_argument('--rows', type=int, default=SEARCH_ROW_LIMIT,
                        help='search rows kept verbatim per case')
    return parser.parse_args()


def digest(values):
    return hashlib.sha1('\x1f'.join(values).encode('utf-8')).hexdigest()


def text_digest(text):
    return hashlib.sha1(text.encode('utf-8')).hexdigest()


def database_state(engine):
    cursor = engine._get_connection().cursor()
    counts = {}
    for table in ('dictionary', 'entry_body', 'sub_headwords', 'content_index'):
        counts[table] = cursor.execute(
            'SELECT COUNT(*) FROM %s' % table).fetchone()[0]
    version = cursor.execute(
        "SELECT value FROM schema_meta WHERE key = 'schema_version'").fetchone()
    content_by_tag = cursor.execute(
        'SELECT tag_type, COUNT(*) FROM content_index '
        'GROUP BY tag_type ORDER BY tag_type').fetchall()
    by_source = cursor.execute(
        'SELECT source_file, COUNT(*) FROM dictionary '
        'GROUP BY source_file ORDER BY source_file').fetchall()
    indexes = cursor.execute(
        "SELECT name, tbl_name FROM sqlite_master "
        "WHERE type = 'index' AND name NOT LIKE 'sqlite_%' "
        'ORDER BY name').fetchall()
    return {
        'schema_version': version[0] if version else None,
        'counts': counts,
        'content_by_tag': [[tag, count] for tag, count in content_by_tag],
        'dictionary_by_source': [[name, count] for name, count in by_source],
        'indexes': ['%s:%s' % (name, table) for name, table in indexes],
    }


def sampled_entries(cursor, limit):
    ids = [row[0] for row in cursor.execute(
        'SELECT dictionary.id '
        'FROM dictionary JOIN entry_body ON entry_body.id = dictionary.id '
        'ORDER BY dictionary.id')]
    if limit <= 0 or limit >= len(ids):
        selected = ids
    elif limit == 1:
        selected = ids[:1]
    else:
        indexes = sorted({round(index * (len(ids) - 1) / (limit - 1))
                          for index in range(limit)})
        selected = [ids[index] for index in indexes]
    if not selected:
        return []
    placeholders = ','.join(['?'] * len(selected))
    return cursor.execute(
        'SELECT dictionary.id, dictionary.headword, entry_body.xml '
        'FROM dictionary JOIN entry_body ON entry_body.id = dictionary.id '
        'WHERE dictionary.id IN (%s) ORDER BY dictionary.id' % placeholders,
        selected).fetchall()


def render_entry(xml_string):
    try:
        return text_digest(format_entry(xml_string))
    except ElementTree.ParseError as exc:
        return 'parse-error:%s' % exc


def entry_state(engine, limit):
    cursor = engine._get_connection().cursor()
    entries = {
        str(entry_id): [headword, render_entry(xml_string)]
        for entry_id, headword, xml_string in sampled_entries(cursor, limit)
    }
    targeted = cursor.execute(
        'SELECT dictionary.id, dictionary.headword, entry_body.xml, '
        'sub_headwords.headword '
        'FROM sub_headwords '
        'JOIN dictionary ON sub_headwords.main_entry_id = dictionary.id '
        'JOIN entry_body ON entry_body.id = dictionary.id '
        'WHERE sub_headwords.headword != dictionary.headword '
        'ORDER BY dictionary.id, sub_headwords.id LIMIT 1').fetchone()
    if targeted is None:
        return {'entries': entries, 'targeted': None}
    entry_id, headword, xml_string, target = targeted
    set_target_subheadword(target)
    try:
        html = render_entry(xml_string)
    finally:
        clear_target()
    return {
        'entries': entries,
        'targeted': {
            'id': entry_id,
            'headword': headword,
            'target': target,
            'html': html,
        },
    }


def search_state(engine, query, mode, sort_order, row_limit):
    if mode == 'translations':
        rows = engine.search(query, search_in_headwords=False,
                             search_in_translations=True,
                             sort_order=sort_order)
    elif mode == 'examples':
        rows = engine.search(query, search_in_headwords=False,
                             search_in_examples=True,
                             sort_order=sort_order)
    else:
        rows = engine.search(query, sort_order=sort_order)
    row_keys = []
    previews = []
    for row in rows:
        row_keys.append('\x1e'.join(
            str(value) for value in (row[0], row[1], row[2], row[3], row[6])))
        for preview in row[5] or ():
            previews.append('\x1e'.join((
                str(row[0]),
                preview['headword'],
                preview['sort_headword'],
                str(preview['sort_hw_id']),
                '1' if preview['paragraph_break'] else '0',
                text_digest(preview['preview_html']),
            )))
    return {
        'query': query,
        'mode': mode,
        'sort': sort_order,
        'row_count': len(rows),
        'row_digest': digest(row_keys),
        'rows': [[row[0], row[1], row[2], row[3], row[6]]
                 for row in rows[:row_limit]],
        'preview_count': len(previews),
        'preview_digest': digest(previews),
        'previews': previews[:PREVIEW_LIMIT],
    }


def sources_state():
    tree = ElementTree.parse(get_paths()['sources_xml'])
    root = tree.getroot()
    entry = root.find('entry')
    children = list(entry) if entry is not None else []
    section_ids = [child.get('id') for child in children
                   if child.tag == 'section' and child.get('id')]
    anchors = []
    seen = set()
    for abbr in root.iter('abbr'):
        anchor = normalize_anchor(abbr.text)
        if not anchor or anchor in seen:
            continue
        seen.add(anchor)
        anchors.append(anchor)
    cases = []

    def add_case(label, **kwargs):
        cases.append({'case': label,
                      'html': text_digest(build_filtered_html(children, **kwargs))})

    add_case('expanded', collapsed_sections=set())
    add_case('collapsed:' + ','.join(section_ids[:2]),
             collapsed_sections=set(section_ids[:2]))
    add_case('search:' + SOURCES_SEARCH,
             collapsed_sections=set(), search_text=SOURCES_SEARCH)
    add_case('no-match:' + SOURCES_NO_MATCH,
             collapsed_sections=set(), search_text=SOURCES_NO_MATCH)
    for anchor in anchors[:5]:
        add_case('marker:' + anchor, collapsed_sections=set(),
                 marker_anchor=anchor)
    return {'anchors': anchors[:5], 'cases': cases}


def see_state(engine):
    blocks = SourceBlocks(engine)
    analyzer = BrokenLinkAnalyzer(engine._get_connection, blocks.iter_blocks)
    state = {}
    for occurrence in analyzer.see_occurrences():
        key = '%s|%s|%s' % (occurrence['source_file'],
                            occurrence['start'],
                            occurrence['word'])
        row = occurrence['row']
        state[key] = {
            'entry_attr': occurrence['entry_attr'],
            'hw_attr': occurrence['hw_attr'],
            'outcome': occurrence['outcome'],
            'row': [row[0], row[1], row[2], row[3], row[4]] if row else None,
        }
    return state


def build_snapshot(engine, entry_limit, row_limit):
    engine._get_connection().execute('PRAGMA query_only = ON')
    return {
        'snapshot_version': SNAPSHOT_VERSION,
        'database': database_state(engine),
        'entries': entry_state(engine, entry_limit),
        'searches': [search_state(engine, case[0], case[1], case[2], row_limit)
                     for case in SEARCH_CASES],
        'sources': sources_state(),
        'sees': see_state(engine),
    }


def diff_values(golden, current, path=''):
    if type(golden) is not type(current):
        yield path, golden, current
        return
    if isinstance(golden, dict):
        for key in sorted(golden.keys() | current.keys(), key=str):
            child = '%s.%s' % (path, key) if path else str(key)
            if key not in golden:
                yield child, '<absent>', current[key]
            elif key not in current:
                yield child, golden[key], '<absent>'
            else:
                yield from diff_values(golden[key], current[key], child)
        return
    if isinstance(golden, list):
        if len(golden) != len(current):
            yield '%s.length' % path, len(golden), len(current)
        for index, (old, new) in enumerate(zip(golden, current)):
            yield from diff_values(old, new, '%s[%s]' % (path, index))
        return
    if golden != current:
        yield path, golden, current


def short(value, limit=140):
    if isinstance(value, str):
        text = value
    else:
        text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    text = ' '.join(text.split())
    if len(text) > limit:
        return text[:limit] + '...'
    return text


def summary(snapshot):
    return ('%s entries, %s searches, %s sources cases, %s <see> outcomes' % (
        len(snapshot['entries']['entries']),
        len(snapshot['searches']),
        len(snapshot['sources']['cases']),
        len(snapshot['sees']),
    ))


def save_snapshot(snapshot, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, 'w', encoding='utf-8', newline='\n') as handle:
        json.dump(snapshot, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write('\n')
    print('saved baseline: %s' % target)
    print('snapshot: %s' % summary(snapshot))
    return 0


def check_snapshot(snapshot, target, limit=40):
    if not target.exists():
        print('baseline not found: %s' % target, file=sys.stderr)
        print('run with --save first', file=sys.stderr)
        return 2
    try:
        with open(target, 'r', encoding='utf-8-sig') as handle:
            golden = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        print('cannot read baseline %s: %s' % (target, exc), file=sys.stderr)
        return 2
    mismatches = list(diff_values(golden, snapshot))
    if not mismatches:
        print('snapshot matches baseline: %s' % summary(snapshot))
        return 0
    for path, old, new in mismatches[:limit]:
        print('MISMATCH %s' % path)
        print('  baseline: %s' % short(old))
        print('  current:  %s' % short(new))
    if len(mismatches) > limit:
        print('%s more differences' % (len(mismatches) - limit))
    print('FAILED: %s differences against %s' % (len(mismatches), target))
    return 1


def main():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding='utf-8', errors='replace')
        except AttributeError:
            pass
    args = parse_args()
    database = args.database or get_paths()['database']
    if not os.path.exists(database):
        print('database not found: %s' % database, file=sys.stderr)
        print('launch either app once to build it', file=sys.stderr)
        return 2
    engine = SearchEngine(database)
    try:
        snapshot = build_snapshot(engine, args.entries, args.rows)
    except sqlite3.DatabaseError as exc:
        print('database error: %s' % exc, file=sys.stderr)
        return 2
    finally:
        engine.close()
    if args.save is not None:
        return save_snapshot(snapshot, Path(args.save).resolve())
    return check_snapshot(snapshot, Path(args.check).resolve())


if __name__ == '__main__':
    sys.exit(main())
