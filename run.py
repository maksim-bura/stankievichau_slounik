import sys
import os
from PySide6.QtWidgets import QApplication
from db import SearchEngine
from db.build_database import build_database, needs_rebuild, get_paths
from app import MainWindow

if needs_rebuild():
    build_database()

database_path = get_paths()['database']
search_engine = SearchEngine(database_path)

app = QApplication(sys.argv)
window = MainWindow(search_engine)
window.show()
sys.exit(app.exec())
