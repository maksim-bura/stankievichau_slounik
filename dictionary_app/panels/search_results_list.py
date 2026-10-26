from PySide6.QtCore import Qt, QAbstractListModel, QModelIndex, QItemSelectionModel
from PySide6.QtWidgets import QListView
from dictionary_app.utils.collapse_duplicates import collapse_same_entry_duplicates
from dictionary_app.utils.normalize_headword import resolve_headword
from dictionary_app.utils.item_roles import ROLE_HEADWORD
from dictionary_app.theme.layout_constants import RESULTS_MIN_WIDTH
from dictionary_app.widgets import ElidingDelegate, navigate_rows, select_row


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
        display, headword = self.rows[index.row()]
        if role == Qt.DisplayRole:
            return display
        if role == ROLE_HEADWORD:
            return headword
        return None

    def set_rows(self, rows):
        self.beginResetModel()
        self.rows = rows
        self.endResetModel()


class SearchResultsList:
    def __init__(self, search_engine, list_view, entry_viewer, navigation_bar):
        self.search_engine = search_engine
        self._view = list_view
        self._model = ResultsListModel()
        list_view.setModel(self._model)
        self.entry_viewer = entry_viewer
        self.navigation_bar = navigation_bar
        self.current_results = []
        self._by_headword = {}
        self._by_identity = {}
        self._by_id = {}
        self._view.setFixedWidth(RESULTS_MIN_WIDTH)
        self._view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._view.setVerticalScrollMode(QListView.ScrollMode.ScrollPerPixel)
        self._view.setUniformItemSizes(True)
        self._view.setItemDelegate(ElidingDelegate(self._view))

    def display_results(self, results):
        results = collapse_same_entry_duplicates(results)
        self.current_results = results
        self._view.clearSelection()
        self.entry_viewer.clear()

        self._index_results()

        self._model.set_rows([
            (resolve_headword(r[1], r[6] if len(r) > 6 else 0), r[1])
            for r in results
        ])

        if results:
            self._select_row(0)

    def _index_results(self):
        by_headword = {}
        by_identity = {}
        by_id = {}
        for result in self.current_results:
            headword = result[1]
            identity = resolve_headword(headword, result[6] if len(result) > 6 else 0)
            by_headword.setdefault(headword, result)
            by_identity.setdefault(identity, result)
            by_id.setdefault(result[0], result)
        self._by_headword = by_headword
        self._by_identity = by_identity
        self._by_id = by_id

    def find_by_headword(self, headword):
        return self._by_headword.get(headword)

    def find_by_identity(self, identity):
        return self._by_identity.get(identity)

    def find_by_id(self, entry_id):
        return self._by_id.get(entry_id)

    def _select_row(self, row):
        select_row(self._view, self._model, row)

    def navigate(self, direction):
        navigate_rows(self._view, self._model, direction)

    def current_item(self):
        return self._view.currentIndex()

    def on_clicked(self, index, formatter, display_entry, scroll_to_anchor):
        if not index.isValid():
            return
        self._view.clearSelection()
        self._view.selectionModel().setCurrentIndex(index, QItemSelectionModel.SelectionFlag.ClearAndSelect)
        clicked_word = index.data(ROLE_HEADWORD)
        if not clicked_word:
            return
        row = index.row()
        if not (0 <= row < len(self.current_results)):
            return

        result = self.current_results[row]
        if result[2] is None:
            result = self.search_engine.materialize_result(result)
            if result is None:
                return

        return self._present_clicked(result, formatter, display_entry, scroll_to_anchor)

    def _present_clicked(self, result, formatter, display_entry, scroll_to_anchor):
        main_headword = self.search_engine.get_main_headword(result[0], result[2])
        keep_acc = result[6] if len(result) > 6 else 0

        if result[1] != main_headword:
            formatter.set_target_subheadword(result[1])
            applied_target = result[1]
        else:
            formatter.clear_target()
            applied_target = None

        display_entry(result)
        scroll_to_anchor(resolve_headword(result[1], keep_acc))
        self.navigation_bar.clear()
        return applied_target