from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QListWidget, QSplitter, QApplication
)
from PySide6.QtCore import Qt
from format.link_handler import LinkHandler
from utils.accent_utils import remove_accents
from utils.case_utils import compile_search_regex
import format.entry_formatter as formatter
from localization import strings
from db import SearchEngine
from app.widgets import SourcesButton, SettingsButton, SearchBox
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
        self.current_display_xml = None
        self.current_display_xml_id = None
        self.current_display_headword = None
        self.sources_panel = SourcesPanel(self)
        self.sources_visible = False
        self.sources_toggle = SourcesToggle(self)

        self.setWindowTitle(strings.window.title)
        self.resize(WINDOW_DEFAULT_WIDTH, WINDOW_DEFAULT_HEIGHT)

        self.results_visible = True
        self.entry_min_width = ENTRY_MIN_WIDTH
        self._search_pattern = None
        self._search_normalize = False
        self._search_in_headwords = False
        self._highlight_entry = False
        self._highlighted_entry_id = None
        self.sources_min_width = SOURCES_MIN_WIDTH
        self.results_min_width = RESULTS_MIN_WIDTH

        self.entry_viewer = EntryViewer(self, self.open_entry_by_headword_nav)
        self.entry_scroll_manager = self.entry_viewer.scroll_manager

        self.setup_ui()
        self.load_styles()
        install_global_copy(self)

        self.results_list = SearchResultsList(
            self, search_engine,
            self.results_box, self.entry_viewer,
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

    def open_entry_by_headword(self, headword, sense_parts=None, entry_link=None, from_navigation=False):
        if headword == '__preview__':
            self._restore_preview()
            return

        target_headword = remove_accents(headword)
        result_to_display = None
        old_headword = self.current_display_headword

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
            root = self.search_engine.get_parsed_entry(result_to_display[0], result_to_display[2])
            main_headword_element = root.find('hw')
            main_headword = remove_accents(main_headword_element.text) if main_headword_element is not None else ""
            compare_to = target_headword

            if sense_parts:
                formatter.set_target_senses(sense_parts, headword)
            elif compare_to != main_headword:
                formatter.set_target_subheadword(compare_to)
            else:
                formatter.clear_target()

            self.display_entry(result_to_display)

            if not from_navigation and result_to_display[1] != old_headword:
                if old_headword is None and getattr(self, '_last_preview_html', None):
                    old_headword = '__preview__'
                self.entry_viewer.navigation_bar.push(result_to_display[1], sense_parts, old_headword)

            if sense_parts:
                anchor_id = f"sense_{sense_parts[0]}" if sense_parts else None
                if anchor_id:
                    self.entry_scroll_manager.scroll_to_anchor(anchor_id)
            elif entry_link and '#' in entry_link:
                anchor = entry_link.split('#')[1]
                self.entry_scroll_manager.scroll_to_anchor(anchor)
            else:
                self.entry_scroll_manager.scroll_to_anchor(compare_to)

    def on_link_clicked(self, url):
        url_string = url.toString()
        if url_string.startswith("preview:"):
            rest = url_string[8:]
            if '%' in rest:
                from urllib.parse import unquote
                rest = unquote(rest)
            parts = rest.split('|', 1)
            anchor = parts[1] if len(parts) > 1 else None
            if parts[0].isdigit():
                entry_id = int(parts[0])
                result = None
                for r in self.results_list.current_results:
                    if r[0] == entry_id:
                        result = r
                        break
                if not result:
                    conn = self.search_engine._get_connection()
                    row = conn.cursor().execute(
                        "SELECT id, headword, full_entry, entry_link FROM dictionary WHERE id = ?",
                        (entry_id,)
                    ).fetchone()
                    if row:
                        result = row
                if result:
                    self._highlight_entry = True
                    self._last_preview_html = self.entry_viewer.stored_html
                    self.entry_viewer.navigation_bar.push(result[1], None, '__preview__')
                    if anchor:
                        root = self.search_engine.get_parsed_entry(result[0], result[2])
                        main_hw = root.find('hw')
                        main_headword = remove_accents(main_hw.text) if main_hw is not None else ""
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

        top_layout.addWidget(self.search_box, 1)
        top_layout.addWidget(self.sources_button)
        top_layout.addWidget(self.settings_button)

        self.results_box = QListWidget()
        self.results_box.setFocusPolicy(Qt.NoFocus)
        self.results_box.setStyleSheet(
            "QListWidget::item { border-left: 3px solid transparent; }"
            "QListWidget::item:hover {"
            "  border-left: 3px solid #c0c0c0;"
            "  background: #fafafa;"
            "  color: black;"
            "}"
            "QListWidget::item:selected {"
            "  border-left: 3px solid #7c9ec0;"
            "  background: #edf7fd;"
            "  color: black;"
            "}"
            "QListWidget::item:selected:!active {"
            "  border-left: 3px solid #7c9ec0;"
            "  background: #edf7fd;"
            "  color: black;"
            "}"
        )
        self.results_box.itemClicked.connect(self.on_result_clicked)
        self.results_box.setMinimumWidth(self.results_min_width)

        self.bottom_splitter = QSplitter(Qt.Horizontal)
        entry_widget = self.entry_viewer.get_widget()
        entry_widget.setMinimumWidth(self.entry_min_width)
        self.bottom_splitter.addWidget(entry_widget)
        sources_viewer = self.sources_panel.get_viewer()
        sources_viewer.setMinimumWidth(self.sources_min_width)
        self.bottom_splitter.addWidget(sources_viewer)
        self.bottom_splitter.setCollapsible(0, False)
        self.bottom_splitter.setCollapsible(1, False)
        self.bottom_splitter.setSizes([SPLITTER_ENTRY_INITIAL, SPLITTER_SOURCES_INITIAL])

        bottom_layout = QHBoxLayout()
        bottom_layout.setSpacing(0)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.addWidget(self.results_box)
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
        results_width = self.results_min_width if self.results_visible else 0
        self.sources_visible = self.sources_toggle.toggle(
            self.sources_visible, self.sources_panel, self.sources_button,
            results_width, self.bottom_splitter,
            self.entry_min_width, self.sources_min_width,
            self.entry_scroll_manager
        )
        self._update_min_width()

    def _set_results_visible(self, visible):
        if visible == self.results_visible:
            return
        was_visible = self.results_visible
        self.results_visible = visible
        if visible:
            self.results_box.show()
            needed = self.results_min_width + self.entry_min_width
            if self.sources_visible:
                needed += self.sources_min_width
            if self.width() < needed:
                self.resize(needed, self.height())
        else:
            self.results_box.hide()
        self._update_min_width()

    def _update_min_width(self):
        min_w = self.entry_min_width
        if self.results_visible:
            min_w += self.results_min_width
        if self.sources_visible:
            min_w += self.sources_min_width
        self.setMinimumWidth(min_w)

    def show_all_entries(self):
        self._set_results_visible(True)
        options = self.settings_button.get_option_states()
        results = self.search_engine.search("", **options)
        self.results_list.display_results(results)

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

        exclusive_count = sum([options.get('search_in_translations', False), options.get('search_in_examples', False)])
        is_exclusive = exclusive_count == 1 and not options.get('search_in_headwords', True)
        is_combined = options.get('search_in_headwords', False) and options.get('search_in_examples', False) and not options.get('search_in_translations', False)

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
                self.current_display_xml_id = None
                self.current_display_headword = None
                self.entry_viewer.clear()

    def _on_search_mode_changed(self):
        text = self.search_box.text()
        if text.strip():
            self.on_search(text)
        else:
            options = self.settings_button.get_option_states()
            exclusive = (
                options.get('search_in_translations', False) + options.get('search_in_examples', False) == 1
                and not options.get('search_in_headwords', True)
            )
            self._set_results_visible(not exclusive)

    def _on_keyboard_activate(self):
        item = self.results_list.current_item()
        if item:
            self.on_result_clicked(item)

    def on_result_clicked(self, item):
        options = self.settings_button.get_option_states()
        is_combined = options.get('search_in_headwords', False) and options.get('search_in_examples', False) and not options.get('search_in_translations', False)
        self._highlight_entry = False
        self.results_list.on_clicked(
            item, formatter,
            lambda r: self.display_entry(r),
            self.entry_scroll_manager.scroll_to_anchor
        )
        if is_combined and getattr(self, '_last_preview_html', None):
            headword = item.data(Qt.UserRole + 1)
            if headword:
                self.entry_viewer.navigation_bar.push(headword, None, '__preview__')

    def _show_previews(self, results, translations_mode=False):
        self.current_display_headword = None
        groups = {}
        for result in results:
            if len(result) > 4 and result[4]:
                for p in result[4]:
                    key = (result[0], p['headword'])
                    if key not in groups:
                        groups[key] = {'headword': remove_accents(p['headword']), 'htmls': [], 'breaks': [], 'rank': p.get('rank', 7), 'word_pos': p.get('word_pos', 999), 'word_len': p.get('word_len', 999)}
                    if p['preview_html'] not in groups[key]['htmls']:
                        groups[key]['htmls'].append(p['preview_html'])
                        groups[key]['breaks'].append(p.get('paragraph_break', False))
                        r = p.get('rank', 7)
                        if r < groups[key]['rank']:
                            groups[key]['rank'] = r
                            groups[key]['word_pos'] = p.get('word_pos', 999)
                            groups[key]['word_len'] = p.get('word_len', 999)
                        elif r == groups[key]['rank']:
                            wp = p.get('word_pos', 999)
                            if wp < groups[key]['word_pos']:
                                groups[key]['word_pos'] = wp
                                groups[key]['word_len'] = p.get('word_len', 999)
                            elif wp == groups[key]['word_pos']:
                                wl = p.get('word_len', 999)
                                if wl < groups[key]['word_len']:
                                    groups[key]['word_len'] = wl
        if not groups:
            return
        html_parts = ['<body>']
        first_group = True
        for key in sorted(groups, key=lambda k: (groups[k]['rank'], groups[k]['word_pos'], groups[k]['word_len'], k[1].lower())):
            g = groups[key]
            if not first_group:
                html_parts.append('<br><br>')
            first_group = False
            headword_display = g["headword"].replace("|", ", ")
            anchor_id = g["headword"].split("|")[0]
            html_parts.append(f'<b><a href="preview:{key[0]}|{anchor_id}">{headword_display}</a></b><br>')
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
        self.current_display_xml = result[2]
        self.current_display_xml_id = result[0]
        self.current_display_headword = result[1]
        self.entry_viewer.display_entry(result, formatter)
        self.entry_scroll_manager.last_anchor = None
        should_highlight = self._highlight_entry or (self._search_pattern and self._highlighted_entry_id == result[0])
        if should_highlight and self._search_pattern:
            html = self.entry_viewer.stored_html
            if html:
                exclude = {'hw'}
                if self._search_normalize:
                    exclude.add('ex')
                if self._search_in_headwords:
                    exclude.add('t')
                highlighted = self.search_engine._apply_highlight(html, self._search_pattern, normalize=self._search_normalize, exclude_classes=exclude or None)
                self.entry_viewer.display_html(highlighted)
                self._highlighted_entry_id = result[0]
        self._highlight_entry = False

    def _restore_preview(self):
        if getattr(self, '_last_preview_html', None):
            self.current_display_xml = None
            self.current_display_xml_id = None
            self.current_display_headword = None
            self.entry_viewer.display_html(self._last_preview_html)
            self.entry_viewer.navigation_bar.clear()
