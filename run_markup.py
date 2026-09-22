import sys
from PySide6.QtWidgets import QApplication
from db.bootstrap import create_search_engine
from markup import MarkupMainWindow

app = QApplication(sys.argv)
window = MarkupMainWindow(create_search_engine())
window.show()
sys.exit(app.exec())