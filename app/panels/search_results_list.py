import xml.etree.ElementTree as ElementTree
from PySide6.QtWidgets import QListWidgetItem
from PySide6.QtCore import Qt
from utils.accent_utils import remove_accents
from theme.layout_constants import RESULTS_MIN_WIDTH, ENTRY_LIST_WIDTH_PADDING


class SearchResultsList:
    def __init__(self, parent_window, search_engine, results_list, entry_viewer, entry_scroll_manager, navigation_bar):
        self.parent = parent_window
        self.search_engine = search_engine
        self.results_list = results_list
        self.entry_viewer = entry_viewer
        self.entry_scroll_manager = entry_scroll_manager
        self.navigation_bar = navigation_bar
        self.current_results = []
        self.all_words = None

    def set_width(self):
        if self.all_words is None:
            results = self.search_engine.search("")
            self.all_words = [r[1] for r in results if r[1] != "!SOURCES"]

        if not self.all_words:
            self.results_list.setFixedWidth(RESULTS_MIN_WIDTH)
            return

        font = self.results_list.font()
        font.setBold(True)
        font_metrics = self.results_list.fontMetrics()

        max_width = 0
        for word in self.all_words:
            text_width = font_metrics.horizontalAdvance(word)
            if text_width > max_width:
                max_width = text_width

        final_width = max_width + ENTRY_LIST_WIDTH_PADDING if max_width > 0 else RESULTS_MIN_WIDTH
        self.results_list.setFixedWidth(final_width)

    def display_results(self, results):
        self.current_results = results
        self.results_list.clear()
        self.entry_viewer.clear()
        self.entry_scroll_manager.clear_cache()

        for result in self.current_results:
            display_word = remove_accents(result[1])
            item = QListWidgetItem(display_word)
            item.setData(Qt.UserRole, result[3] if len(result) > 3 else None)
            self.results_list.addItem(item)

    def on_clicked(self, item, formatter, display_entry, scroll_to_anchor):
        clicked_word = item.text()
        entry_link = item.data(Qt.UserRole)

        for result in self.current_results:
            if remove_accents(result[1]) == clicked_word:
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
                scroll_to_anchor(clicked_word)
                self.navigation_bar.clear()
                return
