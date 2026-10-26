import os
import sys
from PySide6.QtWidgets import QApplication

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dictionary_app.db.create_search_engine import create_search_engine
from markup_app import MarkupMainWindow

app = QApplication(sys.argv)
window = MarkupMainWindow(create_search_engine())
window.show()
sys.exit(app.exec())