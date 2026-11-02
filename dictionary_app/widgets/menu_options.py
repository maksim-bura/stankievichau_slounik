from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel

from dictionary_app.theme.layout_constants import MENU_OPTION_MARGINS, SEARCH_BOX_HEIGHT
from dictionary_app.theme.styles import COLOR_DISABLED_FG
from dictionary_app.utils.constants import CHECK_MARK, CHECK_BLANK, RADIO_ON, RADIO_OFF
from dictionary_app.widgets.emoji_label import set_emoji_prefixed_text


class ToggleOption(QWidget):
    def __init__(self, text, glyph_checked, glyph_unchecked, checked=False, parent=None):
        super().__init__(parent)
        self._checked = checked
        self._text = text
        self._glyph_checked = glyph_checked
        self._glyph_unchecked = glyph_unchecked
        self._label = QLabel(self)
        layout = QHBoxLayout(self)
        layout.addWidget(self._label)
        self.setMinimumHeight(SEARCH_BOX_HEIGHT)
        layout.setContentsMargins(*MENU_OPTION_MARGINS)
        self._update_display()

    def _update_display(self):
        prefix = self._glyph_checked if self._checked else self._glyph_unchecked
        set_emoji_prefixed_text(self._label, prefix, self._text)

    def set_checked(self, checked):
        self._checked = checked
        self._update_display()

    def is_checked(self):
        return self._checked

    def mouseReleaseEvent(self, event):
        event.accept()


class CheckOption(ToggleOption):
    clicked = Signal(object)

    def __init__(self, text, checked=False, parent=None):
        self._active = True
        super().__init__(text, CHECK_MARK, CHECK_BLANK, checked, parent)

    def _update_display(self):
        super()._update_display()
        if not self._active:
            self._label.setStyleSheet(f'color: {COLOR_DISABLED_FG};')
        else:
            self._label.setStyleSheet('')

    def set_active(self, active):
        self._active = active
        self._update_display()

    def mousePressEvent(self, event):
        event.accept()
        if self._active:
            self._checked = not self._checked
            self._update_display()
            self.clicked.emit(self)


class RadioOption(ToggleOption):
    toggled = Signal(object)

    def __init__(self, text, checked=False, parent=None):
        super().__init__(text, RADIO_ON, RADIO_OFF, checked, parent)

    def mousePressEvent(self, event):
        event.accept()
        if not self._checked:
            self._checked = True
            self._update_display()
            self.toggled.emit(self)
