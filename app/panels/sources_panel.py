import os
import xml.etree.ElementTree as ElementTree
from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget, QGridLayout, QHBoxLayout
from PySide6.QtCore import Qt
from utils.scroll_manager import ScrollManager
from localization import strings
from theme.layout_constants import (
    BUTTON_SIZE, BAR_CONTENTS_MARGINS, BAR_SPACING,
)
from app.widgets import IconButton, SearchBox, DictTextBrowser
from theme.widget_styles import ENTRY_STYLESHEET
from app.panels.sources_renderer import build_filtered_html, compile_search_regex, section_matches


class SourcesPanel:
    ARROW_MARKER = '\u27a1\ufe0f'

    def __init__(self, parent_window):
        self.parent = parent_window
        self.sources_visible = False
        self.search_visible = False
        self.original_content = None
        self.content = None
        self.current_anchor = None
        self._all_children = None
        self.load_content()

        self.container = QWidget()
        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        self.search_container = QWidget()
        self.search_container.setAutoFillBackground(False)
        search_layout = QHBoxLayout()
        search_layout.setContentsMargins(*BAR_CONTENTS_MARGINS)
        search_layout.setSpacing(BAR_SPACING)

        self.search_line = SearchBox(strings.placeholder.sources_search)
        self.search_line.setClearButtonEnabled(False)
        self.search_line.setVisible(False)
        self.search_line.textChanged.connect(self._on_search)
        search_layout.addWidget(self.search_line, 1)

        self.close_search_button = IconButton("\u274c", flat=True)
        self.close_search_button.setFixedSize(BUTTON_SIZE)
        self.close_search_button.setVisible(False)
        self.close_search_button.clicked.connect(self.close_search_bar)

        search_layout.addWidget(self.close_search_button)

        self.search_container.setLayout(search_layout)
        self.layout.addWidget(self.search_container)

        self.floating_button = IconButton("\U0001f50d", flat=True)
        self.floating_button.setFixedSize(BUTTON_SIZE)
        self.floating_button.clicked.connect(self.open_search_bar)

        self.viewer_wrapper = QWidget()
        self.viewer_wrapper.setAutoFillBackground(False)
        wrapper_layout = QGridLayout()
        wrapper_layout.setContentsMargins(0, 0, 0, 0)
        wrapper_layout.setSpacing(0)

        self.viewer = DictTextBrowser()
        self.viewer.setReadOnly(True)
        self.viewer.setOpenExternalLinks(False)
        self.viewer.anchorClicked.connect(self._on_anchor_clicked)
        self.viewer.setFocusPolicy(Qt.NoFocus)
        self.viewer.document().setDefaultStyleSheet(ENTRY_STYLESHEET)
        wrapper_layout.addWidget(self.viewer, 0, 0)

        wrapper_layout.addWidget(self.floating_button, 0, 0, alignment=Qt.AlignTop | Qt.AlignRight)

        self.viewer_wrapper.setLayout(wrapper_layout)
        self.layout.addWidget(self.viewer_wrapper)

        self.container.setLayout(self.layout)
        self.container.hide()

        self.scroll_manager = ScrollManager(self.viewer)

        self._collapsed_sections = set()
        self._pre_search_content = None
        self._pre_search_collapsed = None
        if self._all_children:
            self.content = build_filtered_html(self._all_children, self._collapsed_sections, self.ARROW_MARKER)
            self.original_content = self.content
        else:
            fallback = "<body>No sources found</body>"
            self.content = fallback
            self.original_content = fallback

    def load_content(self):
        sources_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            'data', 'sources.xml'
        )
        tree = ElementTree.parse(sources_path)
        entry = tree.getroot().find('entry')
        self._all_children = list(entry) if entry is not None else []

    def open_search_bar(self):
        self.search_visible = True
        self._pre_search_content = self.content
        self._pre_search_collapsed = set(self._collapsed_sections)
        self.search_line.setVisible(True)
        self.close_search_button.setVisible(True)
        self.floating_button.setVisible(False)
        self.search_line.setFocus()

    def close_search_bar(self):
        self.search_visible = False
        self.search_line.clear()
        self.search_line.setVisible(False)
        self.close_search_button.setVisible(False)
        self.floating_button.setVisible(True)

    def _toggle_section(self, section_id):
        self._collapsed_sections ^= {section_id}

        old_focus = self.parent.entry_viewer.get_viewer().hasFocus()
        current_scroll = self.viewer.verticalScrollBar().value()

        text = self.search_line.text() if self.search_visible else None
        marker = None if (self.search_visible and text) else self.current_anchor
        self.content = build_filtered_html(self._all_children, self._collapsed_sections, self.ARROW_MARKER, search_text=text, marker_anchor=marker)

        self.viewer.setHtml(self.content)
        self.viewer.verticalScrollBar().setValue(current_scroll)

        if old_focus:
            self.parent.entry_viewer.get_viewer().setFocus()

    def _on_anchor_clicked(self, url):
        url_str = url.toString()
        if url_str.startswith('toggle-section:'):
            section_id = url_str[len('toggle-section:'):]
            self._toggle_section(section_id)
        else:
            self.parent.on_link_clicked(url)

    def scroll_to_source(self, source_abbreviation):
        if self.search_visible:
            self.close_search_bar()
        else:
            self.search_line.clear()

        if not self.original_content:
            return

        anchor = source_abbreviation.rstrip(':').rstrip('.')

        for child in self._all_children:
            if child.tag == 'section' and child.get('id') in self._collapsed_sections:
                for abbr in child.iter('abbr'):
                    if anchor == (abbr.text or '').rstrip(':').rstrip('.'):
                        self._collapsed_sections.discard(child.get('id'))
                        break

        self.current_anchor = anchor
        was_visible = self.sources_visible

        if was_visible:
            old_focus = self.parent.entry_viewer.get_viewer().hasFocus()
            current_scroll = self.viewer.verticalScrollBar().value()

        self.content = build_filtered_html(self._all_children, self._collapsed_sections, self.ARROW_MARKER, marker_anchor=anchor)
        self.viewer.setHtml(self.content)

        if not was_visible:
            self.container.show()
            self.sources_visible = True
        else:
            self.viewer.verticalScrollBar().setValue(current_scroll)
            if old_focus:
                self.parent.entry_viewer.get_viewer().setFocus()

        QApplication.processEvents()
        self.scroll_manager.scroll_to_anchor(anchor)

    def _on_search(self, text):
        if not text:
            restored = self._pre_search_content or self.original_content
            self.content = restored
            if self._pre_search_collapsed is not None:
                self._collapsed_sections = self._pre_search_collapsed
            self.viewer.setHtml(self.content)
            self._pre_search_content = None
            self._pre_search_collapsed = None
            if self.current_anchor:
                QApplication.processEvents()
                self.scroll_manager.scroll_to_anchor(self.current_anchor)
        else:
            if self._pre_search_content is None:
                self._pre_search_content = self.content
                self._pre_search_collapsed = set(self._collapsed_sections)

            pattern = compile_search_regex(text)
            for child in self._all_children:
                if child.tag == 'section' and child.get('id') in self._collapsed_sections:
                    if section_matches(child, pattern):
                        self._collapsed_sections.discard(child.get('id'))

            self.content = build_filtered_html(self._all_children, self._collapsed_sections, self.ARROW_MARKER, search_text=text)
            self.viewer.setHtml(self.content)

    def toggle(self):
        self.sources_visible = not self.sources_visible
        if self.sources_visible:
            if self.content:
                self.viewer.setHtml(self.content)
                QApplication.processEvents()
                if self.current_anchor:
                    self.scroll_manager.scroll_to_anchor(self.current_anchor)
            self.container.show()
        else:
            self.container.hide()
            self.content = self.original_content
            self._collapsed_sections.clear()
            self.current_anchor = None
            self.scroll_manager.last_anchor = None
            if self.search_visible:
                self.close_search_bar()
        return self.sources_visible

    def handle_resize(self):
        self.scroll_manager.handle_resize()

    def get_viewer(self):
        return self.container


class SourcesToggle:
    def __init__(self, parent_window):
        self.parent = parent_window

    def _handle_showing(self, sizes, results_width, entry_min_width, sources_min_width, entry_current_width, bottom_splitter):
        available = self.parent.width() - results_width
        needed = entry_min_width + sources_min_width

        if available >= needed:
            half = available // 2
            entry_width = half
            sources_width = available - half
        else:
            entry_width = entry_current_width
            sources_width = entry_current_width
            new_width = results_width + entry_width + sources_width
            self.parent.resize(new_width, self.parent.height())

        bottom_splitter.setSizes([results_width, entry_width, sources_width])

    def _handle_hiding(self, sizes, results_width, bottom_splitter, entry_before_hide, sources_before_hide):
        new_entry = entry_before_hide + sources_before_hide
        bottom_splitter.setSizes([results_width, new_entry, 0])

    def _handle_already_visible(self, sizes, results_width, entry_min_width, sources_min_width, bottom_splitter):
        if sizes[2] == 0:
            available = self.parent.width() - results_width
            needed = entry_min_width + sources_min_width
            if available >= needed:
                half = available // 2
                bottom_splitter.setSizes([results_width, half, available - half])

    def _handle_already_hidden(self, sizes, results_width, bottom_splitter):
        bottom_splitter.setSizes([results_width, results_width + sizes[2], 0])

    def toggle(self, sources_visible, sources, sources_button, bottom_splitter, entry_min_width, sources_min_width, entry_scroll_manager):
        was_visible = sources_visible
        sizes_before = bottom_splitter.sizes() if was_visible else None
        sources_visible = sources.toggle()
        sources_button.set_sources_visible(sources_visible)

        sizes = bottom_splitter.sizes()
        results_width = sizes[0]
        entry_current_width = sizes[1]

        if sources_visible and not was_visible:
            self._handle_showing(sizes, results_width, entry_min_width, sources_min_width, entry_current_width, bottom_splitter)
        elif not sources_visible and was_visible:
            entry_before_hide = sizes_before[1] if sizes_before else sizes[1]
            sources_before_hide = sizes_before[2] if sizes_before else 0
            self._handle_hiding(sizes, results_width, bottom_splitter, entry_before_hide, sources_before_hide)
        elif sources_visible:
            self._handle_already_visible(sizes, results_width, entry_min_width, sources_min_width, bottom_splitter)
        else:
            self._handle_already_hidden(sizes, results_width, bottom_splitter)

        return sources_visible
