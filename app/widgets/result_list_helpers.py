from PySide6.QtCore import Qt, QEvent
from PySide6.QtWidgets import QStyledItemDelegate, QToolTip
from theme.layout_constants import RESULTS_ITEM_PADDING


class ElidingDelegate(QStyledItemDelegate):
    def __init__(self, view):
        super().__init__(view)
        self._view = view

    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        text = option.text
        if not text:
            return
        max_width = self._view.viewport().width() - RESULTS_ITEM_PADDING
        if option.fontMetrics.horizontalAdvance(text) > max_width:
            option.text = option.fontMetrics.elidedText(text, Qt.ElideRight, max_width)

    def helpEvent(self, event, view, option, index):
        if event.type() == QEvent.Type.ToolTip:
            text = index.data(Qt.DisplayRole)
            if text:
                max_width = self._view.viewport().width() - RESULTS_ITEM_PADDING
                if option.fontMetrics.horizontalAdvance(text) > max_width:
                    QToolTip.showText(event.globalPos(), text, view)
                    return True
        return super().helpEvent(event, view, option, index)


def clamped_row(current, direction, count):
    if count == 0:
        return None
    current = current if current >= 0 else 0
    new_row = current + direction
    if 0 <= new_row < count:
        return new_row
    return None


def select_row(list_widget, row):
    list_widget.clearSelection()
    item = list_widget.item(row)
    if item:
        item.setSelected(True)
        list_widget.setCurrentItem(item)
        list_widget.scrollToItem(item)


def navigate_rows(list_widget, direction):
    new_row = clamped_row(list_widget.currentRow(), direction, list_widget.count())
    if new_row is not None:
        select_row(list_widget, new_row)