from PySide6.QtCore import Qt
from PySide6.QtWidgets import QStyledItemDelegate
from theme.layout_constants import RESULTS_ITEM_PADDING


class ElidingDelegate(QStyledItemDelegate):
    def __init__(self, list_widget):
        super().__init__(list_widget)
        self._list = list_widget

    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        text = option.text
        if not text:
            return
        max_width = self._list.viewport().width() - RESULTS_ITEM_PADDING
        if option.fontMetrics.horizontalAdvance(text) > max_width:
            option.text = option.fontMetrics.elidedText(text, Qt.ElideRight, max_width)


def select_row(list_widget, row):
    list_widget.clearSelection()
    item = list_widget.item(row)
    if item:
        item.setSelected(True)
        list_widget.setCurrentItem(item)
        list_widget.scrollToItem(item)


def navigate_rows(list_widget, direction):
    row = list_widget.currentRow()
    if row < 0:
        row = 0
    count = list_widget.count()
    if count == 0:
        return
    new_row = row + direction
    if 0 <= new_row < count:
        select_row(list_widget, new_row)