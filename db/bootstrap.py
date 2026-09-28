from db import SearchEngine
from db.build_database import build_database, stale_source_files, get_paths


def create_search_engine():
    stale_files = stale_source_files()
    if stale_files:
        build_database(stale_files)
    return SearchEngine(get_paths()['database'])