import xml.etree.ElementTree as ElementTree
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QListWidget, QSplitter, QApplication
)
from PySide6.QtCore import Qt
from format.link_handler import LinkHandler
from utils.accent_utils import remove_accents
import format.entry_formatter as formatter
from localization import strings
from db import SearchEngine
from app.widgets import SourcesButton, SearchBox
from app.shortcuts.shortcuts import install_global_copy
from app.panels import SearchResultsList, EntryViewer, SourcesPanel
from app.panels.sources_panel import SourcesToggle
from theme.layout_constants import (
    RESULTS_MIN_WIDTH, ENTRY_MIN_WIDTH, SOURCES_MIN_WIDTH,
    WINDOW_DEFAULT_WIDTH, WINDOW_DEFAULT_HEIGHT, SPLITTER_ENTRY_INITIAL,
    SPLITTER_SOURCES_INITIAL, LAYOUT_MARGINS, LAYOUT_SPACING, TOP_LAYOUT_SPACING
)
from theme.widget_styles import GLOBAL_STYLE


class MainWindow(QMainWindow):
    def __init__(self, search_engine):
        super().__init__()

        self.search_engine = search_engine
        self.link_handler = LinkHandler()
        self.current_display_xml = None
        self.current_display_xml_id = None
        self.current_display_headword = None
        self.sources_panel = SourcesPanel(self)
        self.sources_visible = False
        self.sources_toggle = SourcesToggle(self)

        self.setWindowTitle(strings.window.title)
        self.resize(WINDOW_DEFAULT_WIDTH, WINDOW_DEFAULT_HEIGHT)

        self.entry_min_width = ENTRY_MIN_WIDTH
        self.sources_min_width = SOURCES_MIN_WIDTH
        self.results_min_width = RESULTS_MIN_WIDTH

        self.entry_viewer = EntryViewer(self, self.open_entry_by_headword_nav)
        self.entry_scroll_manager = self.entry_viewer.scroll_manager

        self.setup_ui()
        self.load_styles()
        install_global_copy(self)

        self.results_list = SearchResultsList(
            self, search_engine,
            self.results_widget, self.entry_viewer,
            self.entry_scroll_manager, self.entry_viewer.navigation_bar
        )

        self.show_all_entries()
        self.results_list.set_width()

    def open_entry_by_headword_nav(self, headword, sense_parts):
        self.open_entry_by_headword(headword, sense_parts, from_navigation=True)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if event.oldSize().width() != event.size().width():
            self.sources_panel.handle_resize()
            self.entry_scroll_manager.handle_resize()

    def setup_ui(self):
        central_widget = QWidget()
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(*LAYOUT_MARGINS)
        main_layout.setSpacing(LAYOUT_SPACING)

        top_layout = QHBoxLayout()
        top_layout.setSpacing(TOP_LAYOUT_SPACING)

        self.sources_button = SourcesButton()
        self.sources_button.clicked.connect(self.toggle_sources)

        self.search_box = SearchBox(strings.placeholder.entries_search)
        self.search_box.textChanged.connect(self.on_search)

        top_layout.addWidget(self.search_box, 1)
        top_layout.addWidget(self.sources_button)

        self.bottom_splitter = QSplitter(Qt.Horizontal)

        self.results_widget = QListWidget()
        self.results_widget.itemClicked.connect(self.on_result_clicked)
        self.results_widget.setMinimumWidth(self.results_min_width)
        self.bottom_splitter.addWidget(self.results_widget)

        entry_widget = self.entry_viewer.get_widget()
        entry_widget.setMinimumWidth(self.entry_min_width)
        self.bottom_splitter.addWidget(entry_widget)

        sources_viewer = self.sources_panel.get_viewer()
        sources_viewer.setMinimumWidth(self.sources_min_width)
        self.bottom_splitter.addWidget(sources_viewer)

        self.bottom_splitter.setCollapsible(0, False)
        self.bottom_splitter.setCollapsible(1, False)
        self.bottom_splitter.setCollapsible(2, False)

        self.bottom_splitter.setSizes([RESULTS_MIN_WIDTH, SPLITTER_ENTRY_INITIAL, SPLITTER_SOURCES_INITIAL])

        main_layout.addLayout(top_layout)
        main_layout.addWidget(self.bottom_splitter)
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)

        self._update_min_width()

    def load_styles(self):
        QApplication.instance().setStyleSheet(GLOBAL_STYLE)

    def toggle_sources(self):
        self.sources_visible = self.sources_toggle.toggle(
            self.sources_visible, self.sources_panel, self.sources_button,
            self.bottom_splitter, self.entry_min_width, self.sources_min_width,
            self.entry_scroll_manager
        )
        self._update_min_width()

    def _update_min_width(self):
        min_w = self.results_min_width + self.entry_min_width
        if self.sources_visible:
            min_w += self.sources_min_width
        self.setMinimumWidth(min_w)

    def show_all_entries(self):
        results = self.search_engine.search("")
        self.results_list.display_results(results)

    def on_search(self, text):
        self.entry_viewer.navigation_bar.clear()
        results = self.search_engine.search(text)
        self.results_list.display_results(results)

    def on_result_clicked(self, item):
        self.results_list.on_clicked(
            item, formatter,
            lambda r: self.display_entry(r),
            self.entry_scroll_manager.scroll_to_anchor
        )

    def on_link_clicked(self, url):
        url_string = url.toString()
        link_type, target, sense_parts, entry_link = self.link_handler.process_url(url_string)

        if link_type == 'word' and target:
            self.open_entry_by_headword(target, sense_parts, entry_link, from_navigation=False)
        elif link_type == 'source' and target:
            self.open_source(target)

    def open_source(self, source_abbreviation):
        formatter.clear_target()
        self.entry_scroll_manager.save_scroll()
        if not self.sources_visible:
            self.toggle_sources()
        self.sources_panel.scroll_to_source(source_abbreviation)
        self.entry_viewer.refresh()

    def open_entry_by_headword(self, headword, sense_parts=None, entry_link=None, from_navigation=False):
        target_headword = remove_accents(headword)

        if sense_parts:
            formatter.set_target_senses(sense_parts, headword)
        else:
            result_to_display = None

            if entry_link:
                for result in self.results_list.current_results:
                    if len(result) > 3 and result[3] == entry_link:
                        result_to_display = result
                        break
                if not result_to_display:
                    entry_data = self.search_engine.get_entry_by_id(entry_link)
                    if entry_data:
                        result_to_display = entry_data
            else:
                for result in self.results_list.current_results:
                    if result[1] == headword:
                        result_to_display = result
                        break

                if not result_to_display:
                    for result in self.results_list.current_results:
                        if remove_accents(result[1]) == target_headword:
                            result_to_display = result
                            break

            if not result_to_display and not entry_link:
                entry_data = self.search_engine.get_entry_by_headword(headword)
                if entry_data[0]:
                    result_to_display = entry_data

            if result_to_display:
                old_headword = self.current_display_headword

                root = ElementTree.fromstring(result_to_display[2])
                main_headword_element = root.find('hw')
                main_headword = remove_accents(main_headword_element.text) if main_headword_element is not None else ""

                compare_to = target_headword

                if compare_to != main_headword:
                    formatter.set_target_subheadword(compare_to)
                else:
                    formatter.clear_target()

                self.display_entry(result_to_display)

                if not from_navigation and result_to_display[1] != old_headword:
                    self.entry_viewer.navigation_bar.push(result_to_display[1], sense_parts, old_headword)

                if entry_link and '#' in entry_link:
                    anchor = entry_link.split('#')[1]
                    self.entry_scroll_manager.scroll_to_anchor(anchor)
                else:
                    self.entry_scroll_manager.scroll_to_anchor(compare_to)

    def display_entry(self, result):
        self.current_display_xml = result[2]
        self.current_display_xml_id = result[0]
        self.current_display_headword = result[1]
        self.entry_viewer.display_entry(result, formatter)
        self.entry_scroll_manager.last_anchor = None
