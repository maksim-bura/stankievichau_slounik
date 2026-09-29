from urllib.parse import unquote

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QListView, QSplitter, QApplication
)
from PySide6.QtCore import Qt
from format.link_handler import LinkHandler
from utils.text_utils import remove_accents, alphabet_sort_key
from utils.search_regex import compile_search_regex
import format.entry_formatter as formatter
from localization import strings
from app.widgets import SourcesButton, SettingsButton, SearchBox, InsertLetterGButton, INSERT_LETTER_G
from app.shortcuts.shortcuts import install_global_copy
from app.panels import SearchResultsList, EntryViewer, SourcesPanel, SourcesToggle
from theme.layout_constants import (
    RESULTS_MIN_WIDTH, ENTRY_MIN_WIDTH, SOURCES_MIN_WIDTH,
    WINDOW_DEFAULT_WIDTH, WINDOW_DEFAULT_HEIGHT, SPLITTER_ENTRY_INITIAL,
    SPLITTER_SOURCES_INITIAL, LAYOUT_MARGINS, LAYOUT_SPACING, TOP_LAYOUT_SPACING
)
from theme.widget_styles import GLOBAL_STYLE, RESULTS_LIST_STYLE
from utils.constants import SCHEME_PREVIEW, SENSE_ANCHOR_PREFIX


_PREVIEW_SENTINEL = '__preview__'


class MainWindow(QMainWindow):
    def __init__(self, search_engine):
        super().__init__()

        self.search_engine = search_engine
        self.current_display_xml = None
        self.current_display_headword = None
        self.sources_panel = SourcesPanel(self)
        self.sources_visible = False
        self.sources_toggle = SourcesToggle(self)

        self.setWindowTitle(strings.window.title)
        self.resize(WINDOW_DEFAULT_WIDTH, WINDOW_DEFAULT_HEIGHT)

        self.results_visible = True
        self._search_pattern = None
        self._search_normalize = False
        self._search_in_headwords = False
        self._highlight_entry = False
        self._highlighted_entry_id = None

        self.entry_viewer = EntryViewer(self, self.open_entry_by_headword_nav)
        self.entry_scroll_manager = self.entry_viewer.scroll_manager

        self.setup_ui()
        self.load_styles()
        install_global_copy(self)

        self.results_list = SearchResultsList(
            search_engine,
            self.results_view, self.entry_viewer,
            self.entry_scroll_manager, self.entry_viewer.navigation_bar
        )

        self.search_box.navigate_up.connect(
            lambda: self.results_list.navigate(-1))
        self.search_box.navigate_down.connect(
            lambda: self.results_list.navigate(1))
        self.search_box.activate.connect(
            lambda: self._on_keyboard_activate())

        self.entry_viewer.navigation_bar.close_button.clicked.connect(self._dismiss_highlight)

    def showEvent(self, event):
        super().showEvent(event)
        if not getattr(self, '_initial_shown', False):
            self._initial_shown = True
            self.show_all_entries()

    def open_entry_by_headword_nav(self, headword, sense_parts):
        self.open_entry_by_headword(headword, sense_parts, from_navigation=True)

    def open_entry_by_headword(self, headword, sense_parts=None, entry_link=None, from_navigation=False, from_word_link=False):
        if headword == _PREVIEW_SENTINEL:
            self._restore_preview()
            return

        target_headword = remove_accents(headword)
        result_to_display = None
        old_headword = self.current_display_headword

        if entry_link:
            result_to_display = self.results_list.find_by_link(entry_link)
            if not result_to_display and '#' in entry_link:
                entry_part = entry_link.split('#', 1)[0]
                result_to_display = self.results_list.find_by_link(entry_part)
            if not result_to_display:
                entry_data = self.search_engine.get_entry_by_link(entry_link)
                if not entry_data[0] and '#' in entry_link:
                    entry_part = entry_link.split('#', 1)[0]
                    entry_data = self.search_engine.get_entry_by_link(entry_part)
                if entry_data[0]:
                    result_to_display = entry_data
        else:
            result_to_display = self.results_list.find_by_headword(headword)
            if not result_to_display:
                result_to_display = self.results_list.find_by_clean_headword(target_headword)
            if not result_to_display:
                entry_data = self.search_engine.get_entry_by_headword(headword)
                if entry_data[0]:
                    result_to_display = entry_data

        if result_to_display:
            result_to_display = self.search_engine.materialize_result(result_to_display) or result_to_display
            main_headword = remove_accents(self.search_engine.get_main_headword(result_to_display[0], result_to_display[2]))
            compare_to = target_headword

            if sense_parts:
                formatter.set_target_senses(sense_parts, headword)
            elif compare_to != main_headword:
                formatter.set_target_subheadword(compare_to)
            elif from_word_link:
                formatter.set_target_subheadword(compare_to)
            else:
                formatter.clear_target()

            self.display_entry(result_to_display)

            if not from_navigation and result_to_display[1] != old_headword:
                if old_headword is None and getattr(self, '_last_preview_html', None):
                    old_headword = _PREVIEW_SENTINEL
                self.entry_viewer.navigation_bar.push(result_to_display[1], sense_parts, old_headword)

            if sense_parts:
                anchor_id = f"{SENSE_ANCHOR_PREFIX}{sense_parts[0]}" if sense_parts else None
                if anchor_id:
                    self.entry_scroll_manager.scroll_to_anchor(anchor_id)
            elif entry_link and '#' in entry_link:
                self.entry_scroll_manager.scroll_to_anchor(entry_link)
            else:
                self.entry_scroll_manager.scroll_to_anchor(compare_to)
        else:
            if not from_navigation and headword != old_headword:
                if old_headword is None and getattr(self, '_last_preview_html', None):
                    old_headword = _PREVIEW_SENTINEL
                self.entry_viewer.navigation_bar.push(headword, sense_parts, old_headword)
            self.current_display_xml = None
            self.current_display_headword = None
            self.entry_viewer.display_html('<body></body>')

    def on_link_clicked(self, url):
        url_string = url.toString()
        preview_prefix = SCHEME_PREVIEW + ':'
        if url_string.startswith(preview_prefix):
            rest = url_string[len(preview_prefix):]
            if '%' in rest:
                rest = unquote(rest)
            parts = rest.split('|', 1)
            anchor = parts[1] if len(parts) > 1 else None
            if parts[0].isdigit():
                entry_id = int(parts[0])
                result = self.results_list.find_by_id(entry_id)
                if not result:
                    result = self.search_engine.get_entry_by_id(entry_id)
                if result:
                    result = self.search_engine.materialize_result(result) or result
                    self._highlight_entry = True
                    self._last_preview_html = self.entry_viewer.stored_html
                    self.entry_viewer.navigation_bar.push(result[1], None, _PREVIEW_SENTINEL)
                    if anchor:
                        main_headword = remove_accents(self.search_engine.get_main_headword(result[0], result[2]))
                        if anchor != main_headword:
                            formatter.set_target_subheadword(anchor)
                        else:
                            formatter.clear_target()
                    else:
                        formatter.clear_target()
                    self.display_entry(result)
                    if anchor:
                        self.entry_scroll_manager.scroll_to_anchor(anchor)
            return
        link_type, target, sense_parts, entry_link = LinkHandler.process_url(url_string)

        if link_type == 'word' and target:
            self.open_entry_by_headword(target, sense_parts, entry_link, from_navigation=False, from_word_link=True)
        elif link_type == 'source' and target:
            self.open_source(target)

    def open_source(self, source_abbreviation):
        formatter.clear_target()
        self.entry_scroll_manager.cache_scroll()
        if not self.sources_visible:
            self.toggle_sources()
        self.sources_panel.scroll_to_source(source_abbreviation)
        self.entry_viewer.refresh()

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

        self.settings_button = SettingsButton(sources_button=self.sources_button)
        self.settings_button.search_mode_changed.connect(self._on_search_mode_changed)

        self.search_box = SearchBox(strings.placeholder.entries_search)
        self.search_box.textChanged.connect(self.on_search)

        self.insert_letter_g_button = InsertLetterGButton()
        self.insert_letter_g_button.clicked.connect(self._insert_letter_g)

        top_layout.addWidget(self.search_box, 1)
        top_layout.addWidget(self.insert_letter_g_button)
        top_layout.addWidget(self.sources_button)
        top_layout.addWidget(self.settings_button)

        self.results_view = QListView()
        self.results_view.setFocusPolicy(Qt.NoFocus)
        self.results_view.setStyleSheet(RESULTS_LIST_STYLE)
        self.results_view.clicked.connect(self.on_result_clicked)
        self.results_view.setMinimumWidth(RESULTS_MIN_WIDTH)

        self.bottom_splitter = QSplitter(Qt.Horizontal)
        entry_widget = self.entry_viewer.get_widget()
        entry_widget.setMinimumWidth(ENTRY_MIN_WIDTH)
        self.bottom_splitter.addWidget(entry_widget)
        sources_viewer = self.sources_panel.get_widget()
        sources_viewer.setMinimumWidth(SOURCES_MIN_WIDTH)
        self.bottom_splitter.addWidget(sources_viewer)
        self.bottom_splitter.setCollapsible(0, False)
        self.bottom_splitter.setCollapsible(1, False)
        self.bottom_splitter.setSizes([SPLITTER_ENTRY_INITIAL, SPLITTER_SOURCES_INITIAL])

        bottom_layout = QHBoxLayout()
        bottom_layout.setSpacing(LAYOUT_SPACING)
        bottom_layout.setContentsMargins(*LAYOUT_MARGINS)
        bottom_layout.addWidget(self.results_view)
        bottom_layout.addWidget(self.bottom_splitter)
        bottom_layout.setStretch(0, 0)
        bottom_layout.setStretch(1, 1)

        main_layout.addLayout(top_layout)
        main_layout.addLayout(bottom_layout)
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)

        self._update_min_width()

    def load_styles(self):
        QApplication.instance().setStyleSheet(GLOBAL_STYLE)

    def toggle_sources(self):
        results_width = RESULTS_MIN_WIDTH if self.results_visible else 0
        self.sources_visible = self.sources_toggle.toggle(
            self.sources_visible, self.sources_panel, self.sources_button,
            results_width, self.bottom_splitter,
            ENTRY_MIN_WIDTH, SOURCES_MIN_WIDTH
        )
        self._update_min_width()

    def _set_results_visible(self, visible):
        if visible == self.results_visible:
            return
        self.results_visible = visible
        if visible:
            self.results_view.show()
            needed = RESULTS_MIN_WIDTH + ENTRY_MIN_WIDTH
            if self.sources_visible:
                needed += SOURCES_MIN_WIDTH
            if self.width() < needed:
                self.resize(needed, self.height())
        else:
            self.results_view.hide()
        self._update_min_width()

    def _update_min_width(self):
        min_w = ENTRY_MIN_WIDTH
        if self.results_visible:
            min_w += RESULTS_MIN_WIDTH
        if self.sources_visible:
            min_w += SOURCES_MIN_WIDTH
        self.setMinimumWidth(min_w)

    def show_all_entries(self):
        self._set_results_visible(True)
        options = self.settings_button.get_option_states()
        results = self.search_engine.search("", **options)
        self.results_list.display_results(results)

    @staticmethod
    def _is_exclusive(options):
        return (options.get('search_in_translations', False) + options.get('search_in_examples', False) == 1
                and not options.get('search_in_headwords', True))

    @staticmethod
    def _is_combined(options):
        return (options.get('search_in_headwords', False)
                and options.get('search_in_examples', False)
                and not options.get('search_in_translations', False))

    def on_search(self, text):
        self.entry_viewer.navigation_bar.clear()
        self._highlighted_entry_id = None
        options = self.settings_button.get_option_states()

        if text.strip():
            self._search_pattern = compile_search_regex(text, text.endswith(' '))
            self._search_normalize = options.get('search_in_translations', False) and not options.get('search_in_examples', False)
            self._search_in_headwords = options.get('search_in_headwords', False)
        else:
            self._search_pattern = None

        is_exclusive = self._is_exclusive(options)
        is_combined = self._is_combined(options)

        if is_combined and text.strip():
            self._set_results_visible(True)
            hw_results = self.search_engine.search(text, search_in_headwords=True, search_in_translations=False, search_in_examples=False)
            self.results_list.display_results(hw_results)
            ex_results = self.search_engine.search(text, search_in_headwords=False, search_in_translations=False, search_in_examples=True)
            self._show_previews(ex_results, translations_mode=False)
        elif is_exclusive and text.strip():
            self._set_results_visible(False)
            results = self.search_engine.search(text, **options)
            self.results_list.display_results(results)
            self._show_previews(results, translations_mode=options.get('search_in_translations', False))
        else:
            results = self.search_engine.search(text, **options)
            self.results_list.display_results(results)
            if is_exclusive:
                self._set_results_visible(False)
            else:
                self._set_results_visible(True)
                self.current_display_xml = None
                self.current_display_headword = None
                self.entry_viewer.clear()

    def _insert_letter_g(self):
        focus_widget = QApplication.focusWidget()
        if isinstance(focus_widget, SearchBox):
            focus_widget.insert(INSERT_LETTER_G)
            return
        self.search_box.setFocus()
        self.search_box.insert(INSERT_LETTER_G)

    def _on_search_mode_changed(self):
        text = self.search_box.text()
        if text.strip():
            self.on_search(text)
        else:
            options = self.settings_button.get_option_states()
            self._set_results_visible(not self._is_exclusive(options))

    def _on_keyboard_activate(self):
        index = self.results_list.current_item()
        if index.isValid():
            self.on_result_clicked(index)

    def on_result_clicked(self, index):
        options = self.settings_button.get_option_states()
        is_combined = self._is_combined(options)
        self._highlight_entry = False
        self.results_list.on_clicked(
            index, formatter,
            lambda r: self.display_entry(r),
            self.entry_scroll_manager.scroll_to_anchor
        )
        if is_combined and getattr(self, '_last_preview_html', None):
            headword = index.data(Qt.UserRole + 1)
            if headword:
                self.entry_viewer.navigation_bar.push(headword, None, _PREVIEW_SENTINEL)

    def _show_previews(self, results, translations_mode=False):
        self.current_display_headword = None
        groups = {}
        for result in results:
            if result[5]:
                for p in result[5]:
                    key = (result[0], p['headword'])
                    if key not in groups:
                        groups[key] = {'headword': remove_accents(p['headword']), 'sort_headword': remove_accents(p.get('sort_headword') or p['headword']), 'htmls': [], 'breaks': []}
                    if p['preview_html'] not in groups[key]['htmls']:
                        groups[key]['htmls'].append(p['preview_html'])
                        groups[key]['breaks'].append(p.get('paragraph_break', False))
        if not groups:
            return
        html_parts = ['<body>']
        first_group = True
        for key, g in sorted(groups.items(), key=lambda kv: (alphabet_sort_key(kv[1]['sort_headword']),)):
            if not first_group:
                html_parts.append('<br><br>')
            first_group = False
            headword_display = g["headword"].replace("|", ", ")
            anchor_id = g["headword"].split("|")[0]
            html_parts.append(f'<b><a href="{SCHEME_PREVIEW}:{key[0]}|{anchor_id}">{headword_display}</a></b><br>')
            joined = ''
            for j, h in enumerate(g['htmls']):
                if j > 0:
                    if translations_mode and g['breaks'][j]:
                        joined += '<br>'
                    else:
                        joined += ' '
                joined += h
            html_parts.append(joined)
        html_parts.append('</body>')
        self.entry_viewer.display_html(''.join(html_parts))
        self._last_preview_html = self.entry_viewer.stored_html

    def _dismiss_highlight(self):
        if self.current_display_xml and self._search_pattern:
            html = formatter.format_entry(self.current_display_xml)
            self.entry_viewer.display_html(html)
        self._search_pattern = None
        self._highlighted_entry_id = None

    def display_entry(self, result):
        if result[2] is None:
            result = self.search_engine.materialize_result(result) or result
        self.current_display_xml = result[2]
        self.current_display_headword = result[1]
        self.entry_viewer.display_entry(result, formatter)
        should_highlight = self._highlight_entry or (self._search_pattern and self._highlighted_entry_id == result[0])
        if should_highlight and self._search_pattern:
            html = self.entry_viewer.stored_html
            if html:
                exclude = {'hw'}
                if self._search_normalize:
                    exclude.add('ex')
                if self._search_in_headwords:
                    exclude.add('t')
                highlighted = self.search_engine.apply_highlight(html, self._search_pattern, normalize=self._search_normalize, exclude_classes=exclude or None)
                self.entry_viewer.display_html(highlighted)
                self._highlighted_entry_id = result[0]
        self._highlight_entry = False

    def _restore_preview(self):
        if getattr(self, '_last_preview_html', None):
            self.current_display_xml = None
            self.current_display_headword = None
            self.entry_viewer.display_html(self._last_preview_html)
            self.entry_viewer.navigation_bar.clear()
