import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from PySide6.QtWidgets import QApplication
from db.bootstrap import create_search_engine
from markup import MarkupMainWindow

app = QApplication(sys.argv)
window = MarkupMainWindow(create_search_engine())
window.show()
sys.exit(app.exec())