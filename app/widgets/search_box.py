from PySide6.QtWidgets import QLineEdit
from theme.layout_constants import SEARCH_BOX_HEIGHT
from theme.widget_styles import SEARCH_BOX_STYLE


class SearchBox(QLineEdit):
    def __init__(self, placeholder, parent=None):
        super().__init__(parent)
        self.setPlaceholderText(placeholder)
        self.setFixedHeight(SEARCH_BOX_HEIGHT)
        self.setStyleSheet(SEARCH_BOX_STYLE)
