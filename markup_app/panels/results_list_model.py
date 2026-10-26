from PySide6.QtCore import Qt, QAbstractListModel, QModelIndex

from dictionary_app.utils.item_roles import (
    ROLE_ENTRY_LINK, ROLE_HEADWORD, ROLE_ENTRY_ID, ROLE_SOURCE_FILE,
)


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
