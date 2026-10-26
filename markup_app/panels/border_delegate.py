from PySide6.QtGui import QColor, QBrush, QPalette
from PySide6.QtWidgets import QApplication, QStyle, QStyleOptionViewItem

from dictionary_app.theme.styles import (
    COLOR_BORDER_DEFAULT, COLOR_BORDER_SELECTED, COLOR_HOVER_BG,
    COLOR_NORMAL_BG, COLOR_SELECTED_BG,
)
from dictionary_app.utils.item_roles import (
    ROLE_ENTRY_LINK, ROLE_HEADWORD, ROLE_SOURCE_FILE,
)
from dictionary_app.widgets.eliding_delegate import ElidingDelegate
from markup_app.theme.layout_constants import LIST_ITEM_BORDER_WIDTH
from markup_app.theme.styles import (
    COLOR_CHECKED_BG, COLOR_CHECKED_BORDER, COLOR_CHECKED_HOVER_BG,
    COLOR_CHECKED_SELECTED_BG, COLOR_TEXT, COLOR_TRANSPARENT,
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
_COLOR_TEXT = QColor(COLOR_TEXT)


class BorderDelegate(ElidingDelegate):
    def __init__(self, view, checked_state):
        super().__init__(view)
        self._list_view = view
        self._checked_state = checked_state
        self._hovered_row = -1

    def set_hovered_row(self, row):
        if row == self._hovered_row:
            return
        self._hovered_row = row
        self._list_view.viewport().update()

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
