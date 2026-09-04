import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from PySide6.QtWidgets import QApplication
from db import SearchEngine
from db.build_database import build_database, needs_rebuild, get_paths
from markup import MarkupMainWindow


if needs_rebuild():
    build_database()

database_path = get_paths()['database']
search_engine = SearchEngine(database_path)

app = QApplication(sys.argv)
window = MarkupMainWindow(search_engine)
window.show()
sys.exit(app.exec())
