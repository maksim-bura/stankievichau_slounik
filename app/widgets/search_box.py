from PySide6.QtWidgets import QLineEdit
from PySide6.QtCore import Qt, Signal
from theme.layout_constants import SEARCH_BOX_HEIGHT
from theme.widget_styles import SEARCH_BOX_STYLE


class SearchBox(QLineEdit):
    navigate_up = Signal()
    navigate_down = Signal()
    activate = Signal()

    def __init__(self, placeholder, parent=None):
        super().__init__(parent)
        self.setPlaceholderText(placeholder)
        self.setFixedHeight(SEARCH_BOX_HEIGHT)
        self.setStyleSheet(SEARCH_BOX_STYLE)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Up:
            self.navigate_up.emit()
            event.accept()
        elif event.key() == Qt.Key_Down:
            self.navigate_down.emit()
            event.accept()
        elif event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self.activate.emit()
            event.accept()
        else:
            super().keyPressEvent(event)