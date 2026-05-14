import sys
import os
from PySide6.QtWidgets import QApplication
from core.search import SearchEngine
from ui.main_window import MainWindow

def rebuild_database_if_needed():
    database_path = os.path.join(os.path.dirname(__file__), 'build', 'dictionary.db')
    dictionary_path = os.path.join(os.path.dirname(__file__), 'data', 'dictionary.xml')
    sources_path = os.path.join(os.path.dirname(__file__), 'data', 'sources.xml')

    should_rebuild = False

    if not os.path.exists(database_path):
        print("Database not found. Building...")
        should_rebuild = True
    else:
        db_mtime = os.path.getmtime(database_path)
        dict_mtime = os.path.getmtime(dictionary_path)
        sources_mtime = os.path.getmtime(sources_path)
        if dict_mtime > db_mtime or sources_mtime > db_mtime:
            print("Dictionary or sources file changed. Rebuilding database...")
            should_rebuild = True

    if should_rebuild:
        root_dir = os.path.dirname(__file__)
        if root_dir not in sys.path:
            sys.path.insert(0, root_dir)
        data_dir = os.path.join(root_dir, 'data')
        if data_dir not in sys.path:
            sys.path.insert(0, data_dir)
        import build_database
        import importlib
        importlib.reload(build_database)

def main():
    rebuild_database_if_needed()

    app = QApplication(sys.argv)

    database_path = os.path.join(os.path.dirname(__file__), 'build', 'dictionary.db')
    search_engine = SearchEngine(database_path)

    window = MainWindow(search_engine)
    window.show()

    sys.exit(app.exec())

if __name__ == '__main__':
    main()