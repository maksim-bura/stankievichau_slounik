import os
import xml.etree.ElementTree as ElementTree
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QListWidget, QTextBrowser, QSplitter, QApplication
)
from PySide6.QtCore import Qt
from utils.link_handler import LinkHandler
from utils.accent_utils import remove_accents
from utils.scrolling import ScrollManager
import utils.xml_formatter as formatter
from localization import strings
from controllers.search_controller import SearchController
from .buttons import SourcesButton
from .navigation import NavigationBar
from .panels import SourcesToggle, EntryList
from .components.widgets import SearchBox
from .components.constants import (
    RESULTS_MIN_WIDTH, ENTRY_MIN_WIDTH, SOURCES_MIN_WIDTH,
    WINDOW_DEFAULT_WIDTH, WINDOW_DEFAULT_HEIGHT, SPLITTER_ENTRY_INITIAL,
    SPLITTER_SOURCES_INITIAL, LAYOUT_MARGINS, LAYOUT_SPACING, TOP_LAYOUT_SPACING
)


class MainWindow(QMainWindow):
    def __init__(self, search_engine):
        super().__init__()

        self.search_engine = search_engine
        self.link_handler = LinkHandler()
        self.current_display_xml = None
        self.current_display_xml_id = None
        self.current_display_headword = None
        from .sources_window import SourcesWindow
        self.sources = SourcesWindow(self)
        self.sources_visible = False
        self.sources_toggle = SourcesToggle(self)

        self.setWindowTitle(strings.main_window_title)
        self.resize(WINDOW_DEFAULT_WIDTH, WINDOW_DEFAULT_HEIGHT)

        self.entry_min_width = ENTRY_MIN_WIDTH
        self.sources_min_width = SOURCES_MIN_WIDTH
        self.results_min_width = RESULTS_MIN_WIDTH

        self.setup_ui()
        self.load_styles()
        self.entry_scroll_manager = ScrollManager(self.entry_viewer)

        self.entry_list = EntryList(self, None, self.results_list, self.entry_viewer, self.entry_scroll_manager, self.navigation_bar)
        self.search_controller = SearchController(search_engine, self.entry_list)
        self.entry_list.search_controller = self.search_controller

        self.show_all_entries()
        self.entry_list.set_width()

    def open_entry_by_headword_nav(self, headword, sense_parts):
        self.open_entry_by_headword(headword, sense_parts, from_navigation=True)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if event.oldSize().width() != event.size().width():
            self.sources.handle_resize()
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

        self.search_box = SearchBox(strings.search_placeholder)
        self.search_box.textChanged.connect(self.on_search)

        top_layout.addWidget(self.search_box, 1)
        top_layout.addWidget(self.sources_button)

        self.bottom_splitter = QSplitter(Qt.Horizontal)

        self.results_list = QListWidget()
        self.results_list.itemClicked.connect(self.on_result_clicked)
        self.results_list.setMinimumWidth(self.results_min_width)
        self.bottom_splitter.addWidget(self.results_list)

        entry_container = QWidget()
        entry_layout = QVBoxLayout()
        entry_layout.setContentsMargins(*LAYOUT_MARGINS)
        entry_layout.setSpacing(LAYOUT_SPACING)

        self.navigation_bar = NavigationBar(self, self.open_entry_by_headword_nav)
        self.navigation_bar.hide()
        entry_layout.addWidget(self.navigation_bar)

        self.entry_viewer = QTextBrowser()
        self.entry_viewer.setReadOnly(True)
        self.entry_viewer.setOpenExternalLinks(False)
        self.entry_viewer.setFocusPolicy(Qt.StrongFocus)
        self.entry_viewer.anchorClicked.connect(self.on_link_clicked)
        self.entry_viewer.document().setDefaultStyleSheet("""
            a, a:visited { text-decoration: none; color: inherit; }
        """)
        entry_layout.addWidget(self.entry_viewer)

        entry_container.setLayout(entry_layout)
        entry_container.setMinimumWidth(self.entry_min_width)
        self.bottom_splitter.addWidget(entry_container)

        sources_viewer = self.sources.get_viewer()
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

        self.setMinimumWidth(self.results_min_width + self.entry_min_width + self.sources_min_width)

    def load_styles(self):
        css_path = os.path.join(os.path.dirname(__file__), 'styles', 'dictionary.css')
        with open(css_path, 'r', encoding='utf-8') as file:
            css = file.read()
        QApplication.instance().setStyleSheet(css)

    def toggle_sources(self):
        self.sources_visible = self.sources_toggle.toggle(
            self.sources_visible, self.sources, self.sources_button,
            self.bottom_splitter, self.entry_min_width, self.sources_min_width,
            self.entry_scroll_manager
        )

    def show_all_entries(self):
        self.search_controller.search("")

    def on_search(self, text):
        self.navigation_bar.clear()
        self.search_controller.search(text)

    def on_result_clicked(self, item):
        self.entry_list.on_clicked(item, formatter, self.display_entry, self.entry_scroll_manager.scroll_to_anchor)

    def on_link_clicked(self, url):
        url_string = url.toString()
        link_type, target, sense_parts, entry_link = self.link_handler.process_url(url_string)

        if link_type == 'word' and target:
            self.open_entry_by_headword(target, sense_parts, entry_link, from_navigation=False)
        elif link_type == 'source' and target:
            self.open_source(target)

    def open_source(self, source_abbreviation):
        formatter.clear_target()
        if not self.sources_visible:
            self.toggle_sources()
        else:
            self.entry_scroll_manager.cache_state()
        self.sources.scroll_to_source(source_abbreviation)
        self.entry_scroll_manager.restore_state()

    def open_entry_by_headword(self, headword, sense_parts=None, entry_link=None, from_navigation=False):
        target_headword = remove_accents(headword)

        if sense_parts:
            formatter.set_target_senses(sense_parts, headword)
        else:
            result_to_display = None

            if entry_link:
                for result in self.entry_list.current_results:
                    if len(result) > 3 and result[3] == entry_link:
                        result_to_display = result
                        break
                if not result_to_display:
                    entry_data = self.search_engine.get_entry_by_id(entry_link)
                    if entry_data:
                        result_to_display = entry_data
            else:
                for result in self.entry_list.current_results:
                    if result[1] == headword:
                        result_to_display = result
                        break

                if not result_to_display:
                    for result in self.entry_list.current_results:
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
                    self.navigation_bar.push(result_to_display[1], sense_parts, old_headword)

                if entry_link and '#' in entry_link:
                    anchor = entry_link.split('#')[1]
                    self.entry_scroll_manager.scroll_to_anchor(anchor)
                else:
                    self.entry_scroll_manager.scroll_to_anchor(compare_to)

    def display_entry(self, result):
        self.current_display_xml = result[2]
        self.current_display_xml_id = result[0]
        self.current_display_headword = result[1]
        html = formatter.format_entry(result[2])
        self.entry_scroll_manager.cache_state()
        self.entry_viewer.setHtml(html)
        self.entry_scroll_manager.last_anchor = None