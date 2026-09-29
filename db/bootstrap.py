from db import SearchEngine
from db.build_database import build_database, stale_source_files, get_paths, database_schema_is_current


def create_search_engine():
    paths = get_paths()
    stale_files = stale_source_files()
    if stale_files:
        build_database(stale_files)
    elif not database_schema_is_current(paths['database']):
        build_database()
    return SearchEngine(paths['database'])