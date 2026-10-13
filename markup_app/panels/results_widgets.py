from PySide6.QtCore import Qt, QAbstractListModel, QModelIndex, Signal
from PySide6.QtGui import QColor, QBrush, QPalette
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QApplication, QStyle, QStyleOptionViewItem
)

from dictionary_app.widgets import ElidingDelegate
from markup_app.theme.layout_constants import LIST_ITEM_BORDER_WIDTH
from markup_app.theme.widget_styles import (
    COLOR_CHECKED_BG, COLOR_CHECKED_HOVER_BG, COLOR_CHECKED_SELECTED_BG,
    COLOR_CHECKED_BORDER, COLOR_TRANSPARENT,
)
from dictionary_app.theme.layout_constants import MENU_OPTION_MARGINS, SEARCH_BOX_HEIGHT
from dictionary_app.theme.widget_styles import (
    COLOR_DISABLED_FG, COLOR_NORMAL_BG, COLOR_HOVER_BG, COLOR_SELECTED_BG,
    COLOR_BORDER_DEFAULT, COLOR_BORDER_SELECTED,
)
from dictionary_app.utils.constants import CHECK_MARK, CHECK_BLANK
from dictionary_app.utils.item_roles import (
    ROLE_ENTRY_LINK, ROLE_HEADWORD, ROLE_ENTRY_ID, ROLE_SOURCE_FILE,
)


_COLOR_NORMAL_BG = QColor(COLOR_NORMAL_BG)
_COLOR_HOVER_BG = QColor(COLOR_HOVER_BG)
_COLOR_SELECTED_BG = QColor(COLOR_SELECTED_BG)
_COLOR_BORDER_DEFAULT = QColor(COLOR_BORDER_DEFAULT)
_COLOR_BORDER_SELECTED = QColor(COLOR_BORDER_SELECTED)
_COLOR_CHECKED_BG = QColor(COLOR_CHECKED_BG)
_COLOR_CHECKED_HOVER_BG = QColor(COLOR_CHECKED_HOVER_BG)
_COLOR_CHECKED_SELECTED_BG = QColor(COLOR_CHECKED_SELECTED_BG)
_COLOR_CHECKED_BORDER = QColor(COLOR_CHECKED_BORDER)
_COLOR_TRANSPARENT = QColor(COLOR_TRANSPARENT)
_COLOR_TEXT = QColor(0, 0, 0)


class ResultsListModel(QAbstractListModel):
    def __init__(self):
        super().__init__()
        self.rows = []

    def rowCount(self, parent=QModelIndex()):
        if parent.isValid():
            return 0
        return len(self.rows)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self.rows)):
            return None
        display, result = self.rows[index.row()]
        if role == Qt.DisplayRole:
            return display
        if role == ROLE_ENTRY_LINK:
            return result[3]
        if role == ROLE_HEADWORD:
            return result[1]
        if role == ROLE_ENTRY_ID:
            return result[0]
        if role == ROLE_SOURCE_FILE:
            return result[4]
        return None

    def set_rows(self, rows):
        self.beginResetModel()
        self.rows = rows
        self.endResetModel()


def apply_pressed(button):
    button.setProperty("pressed", "true" if button.isChecked() else "false")
    button.style().unpolish(button)
    button.style().polish(button)



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
        self._label.setText(f'{glyph} {self._text}')
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


class BorderDelegate(ElidingDelegate):
    def __init__(self, view, checked_state):
        super().__init__(view)
        self._checked_state = checked_state
        self._hovered_row = -1

    def paint(self, painter, option, index):
        if not index.isValid():
            super().paint(painter, option, index)
            return

        source_file = index.data(ROLE_SOURCE_FILE)
        headword = index.data(ROLE_HEADWORD)
        entry_link = index.data(ROLE_ENTRY_LINK)
        is_checked = source_file and headword and self._checked_state.is_checked(source_file, entry_link, headword)
        is_selected = bool(option.state & QStyle.State_Selected)
        is_hovered = index.row() == self._hovered_row

        if is_checked:
            if is_selected:
                bg = _COLOR_CHECKED_SELECTED_BG
                border = _COLOR_CHECKED_SELECTED_BG
            elif is_hovered:
                bg = _COLOR_CHECKED_HOVER_BG
                border = _COLOR_CHECKED_BORDER
            else:
                bg = _COLOR_CHECKED_BG
                border = _COLOR_CHECKED_BORDER
        else:
            if is_selected:
                bg = _COLOR_SELECTED_BG
                border = _COLOR_BORDER_SELECTED
            elif is_hovered:
                bg = _COLOR_HOVER_BG
                border = _COLOR_BORDER_DEFAULT
            else:
                bg = _COLOR_NORMAL_BG
                border = _COLOR_TRANSPARENT

        painter.save()
        painter.fillRect(option.rect, bg)
        if border.alpha() > 0:
            painter.fillRect(option.rect.x(), option.rect.y(), LIST_ITEM_BORDER_WIDTH, option.rect.height(), border)

        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        opt.backgroundBrush = QBrush(bg)

        palette = opt.palette
        palette.setColor(QPalette.Text, _COLOR_TEXT)
        palette.setColor(QPalette.HighlightedText, _COLOR_TEXT)
        opt.palette = palette

        style = option.widget.style() if option.widget else QApplication.style()
        style.drawControl(QStyle.CE_ItemViewItem, opt, painter, option.widget)

        painter.restore()
