from PySide6.QtWidgets import QPushButton, QLineEdit
from PySide6.QtCore import Qt
from .constants import BUTTON_SIZE, SEARCH_BOX_HEIGHT
from .styles import FLAT_BUTTON_STYLE, SEARCH_BOX_STYLE


class IconButton(QPushButton):
    def __init__(self, icon, parent=None, tooltip=None, flat=True):
        super().__init__(icon, parent)
        self.setFixedSize(BUTTON_SIZE)
        self.setCursor(Qt.PointingHandCursor)
        if flat:
            self.setFlat(True)
            self.setStyleSheet(FLAT_BUTTON_STYLE)
        if tooltip:
            self.setToolTip(tooltip)


class SearchBox(QLineEdit):
    def __init__(self, placeholder, parent=None):
        super().__init__(parent)
        self.setPlaceholderText(placeholder)
        self.setFixedHeight(SEARCH_BOX_HEIGHT)
        self.setStyleSheet(SEARCH_BOX_STYLE)