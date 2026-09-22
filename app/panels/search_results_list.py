from PySide6.QtCore import Qt
from PySide6.QtWidgets import QListWidgetItem
from utils.text_utils import remove_accents
from theme.layout_constants import RESULTS_MIN_WIDTH, RESULTS_ITEM_PADDING
from app.widgets import ElidingDelegate, select_row, navigate_rows


class SearchResultsList:
    def __init__(self, search_engine, list_widget, entry_viewer, entry_scroll_manager, navigation_bar):
        self.search_engine = search_engine
        self._widget = list_widget
        self.entry_viewer = entry_viewer
        self.entry_scroll_manager = entry_scroll_manager
        self.navigation_bar = navigation_bar
        self.current_results = []
        self._widget.setFixedWidth(RESULTS_MIN_WIDTH)
        self._widget.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._widget.setItemDelegate(ElidingDelegate(self._widget))

    def display_results(self, results):
        self.current_results = results
        self._widget.clear()
        self.entry_viewer.clear()
        self.entry_scroll_manager.clear_cache()

        if not results:
            return

        for r in results:
            item = QListWidgetItem(remove_accents(r[1]))
            item.setData(Qt.UserRole, r[3])
            item.setData(Qt.UserRole + 1, r[1])
            self._widget.addItem(item)

        fm = self._widget.fontMetrics()
        viewport = self._widget.viewport()
        rows = self._widget.count()
        row_height = self._widget.sizeHintForRow(0) if rows else 0
        if row_height and row_height * rows > viewport.height():
            vw = viewport.width() - self._widget.verticalScrollBar().sizeHint().width() - RESULTS_ITEM_PADDING
        else:
            vw = viewport.width() - RESULTS_ITEM_PADDING
        for i in range(rows):
            item = self._widget.item(i)
            if fm.horizontalAdvance(item.text()) > vw:
                item.setToolTip(remove_accents(item.data(Qt.UserRole + 1) or item.text()))

        select_row(self._widget, 0)

    def navigate(self, direction):
        navigate_rows(self._widget, direction)

    def current_item(self):
        return self._widget.currentItem()

    def on_clicked(self, item, formatter, display_entry, scroll_to_anchor):
        self._widget.clearSelection()
        item.setSelected(True)
        self._widget.setCurrentItem(item)
        clicked_word = item.data(Qt.UserRole + 1)
        if not clicked_word:
            return
        entry_link = item.data(Qt.UserRole)
        clicked_clean = remove_accents(clicked_word)

        for result in self.current_results:
            if remove_accents(result[1]) == clicked_clean:
                if entry_link and result[3] != entry_link:
                    continue

                main_headword = self.search_engine.get_main_headword(result[0], result[2])

                if result[1] != main_headword:
                    formatter.set_target_subheadword(result[1])
                else:
                    formatter.clear_target()

                display_entry(result)
                scroll_to_anchor(clicked_clean)
                self.navigation_bar.clear()
                return