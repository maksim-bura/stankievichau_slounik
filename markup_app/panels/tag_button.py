from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtWidgets import QPushButton, QTabBar

from markup_app.theme.styles import TAG_BUTTON_STYLE


class UniformTabBar(QTabBar):
    def tabSizeHint(self, index):
        hint = super().tabSizeHint(index)
        widths = [super().tabSizeHint(i).width() for i in range(self.count())]
        return QSize(max(widths), hint.height()) if widths else hint


class TagButton(QPushButton):
    clicked_with_tag = Signal(str)

    def __init__(self, label, tag_name, parent=None):
        super().__init__(label, parent)
        self._tag_name = tag_name
        self.setCursor(Qt.PointingHandCursor)
        self.setFlat(True)
        self.setStyleSheet(TAG_BUTTON_STYLE)
        self.clicked.connect(lambda: self.clicked_with_tag.emit(self._tag_name))
