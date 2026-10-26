from PySide6.QtCore import QItemSelectionModel


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
