import sys
from PySide6.QtWidgets import QApplication
from db.bootstrap import create_search_engine
from app import MainWindow

app = QApplication(sys.argv)
window = MainWindow(create_search_engine())
window.show()
sys.exit(app.exec())