from PySide6.QtCore import Qt, QEvent, QItemSelectionModel
from PySide6.QtWidgets import QStyledItemDelegate, QToolTip
from dictionary_app.theme.layout_constants import RESULTS_ITEM_PADDING


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


def select_row(view, model, row):
    view.clearSelection()
    if not (0 <= row < model.rowCount()):
        return
    index = model.index(row, 0)
    view.selectionModel().setCurrentIndex(
        index, QItemSelectionModel.SelectionFlag.ClearAndSelect)
    view.scrollTo(index)


def navigate_rows(view, model, direction):
    new_row = clamped_row(view.currentIndex().row(), direction, model.rowCount())
    if new_row is not None:
        select_row(view, model, new_row)