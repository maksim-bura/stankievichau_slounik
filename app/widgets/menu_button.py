from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPushButton, QSizePolicy
from theme.layout_constants import BUTTON_SIZE
from theme.widget_styles import MENU_BUTTON_STYLE


class MenuButton(QPushButton):
    def __init__(self, marker, tooltip_text, parent=None):
        super().__init__(marker, parent)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.setFixedSize(BUTTON_SIZE)
        self.setCursor(Qt.PointingHandCursor)
        self.setProperty("class", "menu-button")
        self.setToolTip(tooltip_text)
        self.setStyleSheet(MENU_BUTTON_STYLE)