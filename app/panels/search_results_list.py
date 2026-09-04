from PySide6.QtCore import Qt
from PySide6.QtWidgets import QListWidgetItem, QStyledItemDelegate
from utils.accent_utils import remove_accents
from theme.layout_constants import RESULTS_MIN_WIDTH


class _ElidingDelegate(QStyledItemDelegate):
    def __init__(self, list_widget):
        super().__init__(list_widget)
        self._list = list_widget

    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        text = option.text
        if not text:
            return
        fm = option.fontMetrics
        vw = self._list.viewport().width() - 10
        if fm.horizontalAdvance(text) > vw:
            option.text = fm.elidedText(text, Qt.ElideRight, vw)


class SearchResultsList:
    def __init__(self, parent_window, search_engine, list_widget, entry_viewer, entry_scroll_manager, navigation_bar):
        self.parent = parent_window
        self.search_engine = search_engine
        self._widget = list_widget
        self.entry_viewer = entry_viewer
        self.entry_scroll_manager = entry_scroll_manager
        self.navigation_bar = navigation_bar
        self.current_results = []
        self._widget.setFixedWidth(RESULTS_MIN_WIDTH)
        self._widget.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._widget.setItemDelegate(_ElidingDelegate(self._widget))

    def set_width(self):
        self._widget.setFixedWidth(RESULTS_MIN_WIDTH)

    def _select_row(self, row):
        self._widget.clearSelection()
        item = self._widget.item(row)
        if item:
            item.setSelected(True)
            self._widget.setCurrentItem(item)
            self._widget.scrollToItem(item)

    def display_results(self, results):
        self.current_results = results
        self._widget.clear()
        self.entry_viewer.clear()
        self.entry_scroll_manager.clear_cache()

        if not results:
            return

        for r in results:
            item = QListWidgetItem(remove_accents(r[1]))
            item.setData(Qt.UserRole, r[3] if len(r) > 3 else None)
            item.setData(Qt.UserRole + 1, r[1])
            self._widget.addItem(item)

        fm = self._widget.fontMetrics()
        vw = self._widget.viewport().width() - 10
        for i in range(self._widget.count()):
            item = self._widget.item(i)
            if fm.horizontalAdvance(item.text()) > vw:
                item.setToolTip(remove_accents(item.data(Qt.UserRole + 1) or item.text()))

        if results:
            self._select_row(0)

    def navigate(self, direction):
        row = self._widget.currentRow()
        if row < 0:
            row = 0
        count = self._widget.count()
        if count == 0:
            return
        new_row = row + direction
        if 0 <= new_row < count:
            self._select_row(new_row)

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
                if entry_link and len(result) > 3 and result[3] != entry_link:
                    continue

                root = self.search_engine.get_parsed_entry(result[0], result[2])
                main_headword_element = root.find('hw')
                main_headword = main_headword_element.text if main_headword_element is not None else ""

                if result[1] != main_headword:
                    formatter.set_target_subheadword(result[1])
                else:
                    formatter.clear_target()

                display_entry(result)
                scroll_to_anchor(clicked_clean)
                self.navigation_bar.clear()
                return
