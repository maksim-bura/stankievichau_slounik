from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel

from dictionary_app.theme.layout_constants import MENU_OPTION_MARGINS, SEARCH_BOX_HEIGHT
from dictionary_app.theme.styles import COLOR_DISABLED_FG
from dictionary_app.utils.constants import CHECK_MARK, CHECK_BLANK
from dictionary_app.widgets.emoji_label import set_emoji_prefixed_text


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


class BrokenCheckOption(QWidget):
    clicked = Signal(object)

    def __init__(self, text, checked=False, parent=None):
        super().__init__(parent)
        self._checked = checked
        self._text = text
        self._active = True
        self._label = QLabel(self)
        layout = QHBoxLayout(self)
        layout.addWidget(self._label)
        layout.setContentsMargins(*MENU_OPTION_MARGINS)
        self.setMinimumHeight(SEARCH_BOX_HEIGHT)
        self._update_display()

    def _update_display(self):
        glyph = CHECK_MARK if self._checked else CHECK_BLANK
        set_emoji_prefixed_text(self._label, glyph, self._text)
        if not self._active:
            self._label.setStyleSheet(f'color: {COLOR_DISABLED_FG};')
        else:
            self._label.setStyleSheet('')

    def set_checked(self, checked):
        self._checked = checked
        self._update_display()

    def is_checked(self):
        return self._checked

    def set_active(self, active):
        self._active = active
        self._update_display()

    def mousePressEvent(self, event):
        event.accept()
        if self._active:
            self._checked = not self._checked
            self._update_display()
            self.clicked.emit(self)
