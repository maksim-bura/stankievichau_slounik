from db import SearchEngine
from db.build_database import build_database, needs_rebuild, get_paths


def create_search_engine():
    if needs_rebuild():
        build_database()
    return SearchEngine(get_paths()['database'])