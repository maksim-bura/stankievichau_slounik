import sys
import os
from PySide6.QtWidgets import QApplication
from core import SearchEngine
from ui import MainWindow

database_path = os.path.join(os.path.dirname(__file__), 'build', 'dictionary.db')
search_engine = SearchEngine(database_path)

app = QApplication(sys.argv)
window = MainWindow(search_engine)
window.show()
sys.exit(app.exec())