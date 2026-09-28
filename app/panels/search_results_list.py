from PySide6.QtCore import Qt, QAbstractListModel, QModelIndex, QItemSelectionModel
from PySide6.QtWidgets import QListView
from utils.text_utils import remove_accents
from theme.layout_constants import RESULTS_MIN_WIDTH
from app.widgets import ElidingDelegate, clamped_row


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
        display, headword, entry_link = self.rows[index.row()]
        if role == Qt.DisplayRole:
            return display
        if role == Qt.UserRole:
            return entry_link
        if role == Qt.UserRole + 1:
            return headword
        return None

    def set_rows(self, rows):
        self.beginResetModel()
        self.rows = rows
        self.endResetModel()


class SearchResultsList:
    def __init__(self, search_engine, list_view, entry_viewer, entry_scroll_manager, navigation_bar):
        self.search_engine = search_engine
        self._view = list_view
        self._model = ResultsListModel()
        list_view.setModel(self._model)
        self.entry_viewer = entry_viewer
        self.entry_scroll_manager = entry_scroll_manager
        self.navigation_bar = navigation_bar
        self.current_results = []
        self._by_headword = {}
        self._by_clean = {}
        self._by_link = {}
        self._by_clean_link = {}
        self._by_id = {}
        self._view.setFixedWidth(RESULTS_MIN_WIDTH)
        self._view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._view.setVerticalScrollMode(QListView.ScrollMode.ScrollPerPixel)
        self._view.setUniformItemSizes(True)
        self._view.setItemDelegate(ElidingDelegate(self._view))

    def display_results(self, results):
        self.current_results = results
        self._view.clearSelection()
        self.entry_viewer.clear()
        self.entry_scroll_manager.clear_cache()

        self._index_results()

        self._model.set_rows([(remove_accents(r[1]), r[1], r[3]) for r in results])

        if results:
            self._select_row(0)

    def _index_results(self):
        by_headword = {}
        by_clean = {}
        by_link = {}
        by_clean_link = {}
        by_id = {}
        for result in self.current_results:
            headword = result[1]
            clean = remove_accents(headword)
            entry_link = result[3]
            by_headword.setdefault(headword, result)
            by_clean.setdefault(clean, result)
            by_id.setdefault(result[0], result)
            if entry_link is not None:
                by_link.setdefault(entry_link, result)
                by_clean_link.setdefault((clean, entry_link), result)
        self._by_headword = by_headword
        self._by_clean = by_clean
        self._by_link = by_link
        self._by_clean_link = by_clean_link
        self._by_id = by_id

    def find_by_headword(self, headword):
        return self._by_headword.get(headword)

    def find_by_clean_headword(self, clean_headword):
        return self._by_clean.get(clean_headword)

    def find_by_link(self, entry_link):
        return self._by_link.get(entry_link)

    def find_by_id(self, entry_id):
        return self._by_id.get(entry_id)

    def find_clicked(self, clean_headword, entry_link=None):
        if entry_link:
            return self._by_clean_link.get((clean_headword, entry_link))
        return self._by_clean.get(clean_headword)

    def _select_row(self, row):
        self._view.clearSelection()
        if row < 0 or row >= self._model.rowCount():
            return
        index = self._model.index(row, 0)
        self._view.selectionModel().setCurrentIndex(index, QItemSelectionModel.SelectionFlag.ClearAndSelect)
        self._view.scrollTo(index)

    def navigate(self, direction):
        new_row = clamped_row(self._view.currentIndex().row(), direction, self._model.rowCount())
        if new_row is not None:
            self._select_row(new_row)

    def current_item(self):
        return self._view.currentIndex()

    def on_clicked(self, index, formatter, display_entry, scroll_to_anchor):
        if not index.isValid():
            return
        self._view.clearSelection()
        self._view.selectionModel().setCurrentIndex(index, QItemSelectionModel.SelectionFlag.ClearAndSelect)
        clicked_word = index.data(Qt.UserRole + 1)
        if not clicked_word:
            return
        entry_link = index.data(Qt.UserRole)
        clicked_clean = remove_accents(clicked_word)

        result = self.find_clicked(clicked_clean, entry_link)
        if result is None:
            return

        if result[2] is None:
            result = self.search_engine.materialize_result(result)
            if result is None:
                return

        self._present_clicked(result, clicked_clean, formatter, display_entry, scroll_to_anchor)

    def _present_clicked(self, result, clicked_clean, formatter, display_entry, scroll_to_anchor):
        main_headword = self.search_engine.get_main_headword(result[0], result[2])

        if result[1] != main_headword:
            formatter.set_target_subheadword(result[1])
        else:
            formatter.clear_target()

        display_entry(result)
        scroll_to_anchor(clicked_clean)
        self.navigation_bar.clear()