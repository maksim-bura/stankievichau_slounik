from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QListWidget

from markup_app.theme.styles import ATTRIBUTE_POPUP_STYLE
from markup_app.theme.styles import COLOR_TEXT


class AttributePopup(QListWidget):
    MAX_VISIBLE = 8

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.Tool
            | Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setFocusPolicy(Qt.NoFocus)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setUniformItemSizes(True)
        self.setStyleSheet(ATTRIBUTE_POPUP_STYLE)
        palette = self.palette()
        palette.setColor(QPalette.Text, QColor(COLOR_TEXT))
        palette.setColor(QPalette.HighlightedText, QColor(COLOR_TEXT))
        self.setPalette(palette)
