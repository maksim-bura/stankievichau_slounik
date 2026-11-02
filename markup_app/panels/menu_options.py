from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel

from dictionary_app.theme.layout_constants import MENU_OPTION_MARGINS, SEARCH_BOX_HEIGHT
from dictionary_app.widgets.menu_options import CheckOption


class MenuCommandOption(QWidget):
    def __init__(self, text, callback, parent=None):
        super().__init__(parent)
        self._callback = callback
        label = QLabel(text, self)
        layout = QHBoxLayout(self)
        layout.addWidget(label)
        layout.setContentsMargins(*MENU_OPTION_MARGINS)
        self.setMinimumHeight(SEARCH_BOX_HEIGHT)

    def mousePressEvent(self, event):
        event.accept()
        if event.button() == Qt.LeftButton and self._callback is not None:
            self._callback()

    def mouseReleaseEvent(self, event):
        event.accept()


class BrokenCheckOption(CheckOption):
    pass

