from PySide6.QtWidgets import QPushButton
from PySide6.QtCore import Qt
from dictionary_app.theme.layout_constants import BUTTON_SIZE
from dictionary_app.theme.styles import FLAT_BUTTON_STYLE


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
