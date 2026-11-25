from PySide6.QtCore import Qt, QAbstractListModel, QModelIndex

from dictionary_app.utils.item_roles import (
    ROLE_ENTRY_LINK, ROLE_HEADWORD, ROLE_ENTRY_ID, ROLE_OCCURRENCE,
    ROLE_SOURCE_FILE,
)
from dictionary_app.utils.normalize_headword import resolve_headword


class ResultsListModel(QAbstractListModel):
    def __init__(self):
        super().__init__()
        self.rows = []
        self._occurrences = []

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
        if role == ROLE_OCCURRENCE:
            return self._occurrences[index.row()]
        return None

    def set_rows(self, rows):
        self.beginResetModel()
        self.rows = rows
        self._occurrences = self._build_occurrences(rows)
        self.endResetModel()

    def refresh_occurrences(self):
        occurrences = self._build_occurrences(self.rows)
        changed = occurrences != self._occurrences
        self._occurrences = occurrences
        return changed

    @staticmethod
    def _build_occurrences(rows):
        counts = {}
        occurrences = []
        for _display, result in rows:
            keep_acc = result[6] if len(result) > 6 else 0
            key = (
                result[0], resolve_headword(result[1], keep_acc), result[3])
            occurrences.append(counts.get(key, 0))
            counts[key] = occurrences[-1] + 1
        return occurrences
