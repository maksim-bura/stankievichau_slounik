import os
import xml.etree.ElementTree as ElementTree
from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget, QGridLayout, QHBoxLayout
from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor
from dictionary_app.utils.scroll_state import ScrollState
from dictionary_app.utils.measure_scrollbars import overlay_right_inset
from dictionary_app.localization import strings
from dictionary_app.theme.layout_constants import (
    BUTTON_SIZE, BAR_CONTENTS_MARGINS, BAR_SPACING, LAYOUT_MARGINS, LAYOUT_SPACING
)
from dictionary_app.widgets import IconButton, SearchBox, DictTextBrowser
from dictionary_app.utils.compile_search_regex import compile_search_regex
from dictionary_app.format.render_sources import (
    build_filtered_html, normalize_anchor, section_matches
)
from dictionary_app.utils.constants import (
    ARROW_MARKER, CROSS_MARKER, MAGNIFIER_MARKER, SCHEME_TOGGLE_SECTION
)


class SourcesPanel:

    def __init__(self, main_window):
        self.main_window = main_window
        self.sources_visible = False
        self.search_visible = False
        self.original_content = None
        self.content = None
        self.current_anchor = None
        self._all_children = None
        self._anchor_texts = {}

        self.container = QWidget()
        self.container_layout = QVBoxLayout()
        self.container_layout.setContentsMargins(*LAYOUT_MARGINS)
        self.container_layout.setSpacing(LAYOUT_SPACING)

        self.search_container = QWidget()
        self.search_container.setAutoFillBackground(False)
        search_layout = QHBoxLayout()
        search_layout.setContentsMargins(*BAR_CONTENTS_MARGINS)
        search_layout.setSpacing(BAR_SPACING)

        self.search_line = SearchBox(strings.search_boxes.sources.placeholder)
        self.search_line.setClearButtonEnabled(False)
        self.search_line.setVisible(False)
        self.search_line.textChanged.connect(self._on_search)
        search_layout.addWidget(self.search_line, 1)

        self.close_search_button = IconButton(CROSS_MARKER, flat=True)
        self.close_search_button.setFixedSize(BUTTON_SIZE)
        self.close_search_button.setVisible(False)
        self.close_search_button.clicked.connect(self.close_search_bar)

        search_layout.addWidget(self.close_search_button)

        self.search_container.setLayout(search_layout)
        self.container_layout.addWidget(self.search_container)

        self.floating_button = IconButton(MAGNIFIER_MARKER, flat=True)
        self.floating_button.setFixedSize(BUTTON_SIZE)
        self.floating_button.clicked.connect(self.open_search_bar)

        self.viewer_wrapper = QWidget()
        self.viewer_wrapper.setAutoFillBackground(False)
        wrapper_layout = QGridLayout()
        wrapper_layout.setContentsMargins(*LAYOUT_MARGINS)
        wrapper_layout.setSpacing(LAYOUT_SPACING)

        self.viewer = DictTextBrowser()
        self.viewer.setReadOnly(True)
        self.viewer.setOpenExternalLinks(False)
        self.viewer.anchorClicked.connect(self._on_anchor_clicked)
        self.viewer.setFocusPolicy(Qt.NoFocus)
        wrapper_layout.addWidget(self.viewer, 0, 0, 1, 2)
        wrapper_layout.setColumnStretch(0, 1)
        wrapper_layout.setColumnStretch(1, 0)
        wrapper_layout.setColumnMinimumWidth(1, 0)

        wrapper_layout.addWidget(self.floating_button, 0, 0, alignment=Qt.AlignTop | Qt.AlignRight)

        self.viewer_wrapper.setLayout(wrapper_layout)
        self.container_layout.addWidget(self.viewer_wrapper)

        self._overlay_layout = wrapper_layout
        self.viewer.verticalScrollBar().rangeChanged.connect(self._update_floating_button_inset)

        self.container.setLayout(self.container_layout)
        self.container.hide()

        self.scroll_manager = ScrollState(self.viewer)

        self._collapsed_sections = set()
        self._pre_search_content = None
        self._pre_search_collapsed = None

    def _ensure_loaded(self):
        if self._all_children is not None:
            return
        self.load_content()
        if self._all_children:
            self.content = build_filtered_html(self._all_children, self._collapsed_sections)
        else:
            self.content = '<body></body>'
        self.original_content = self.content

    def load_content(self):
        sources_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'data', 'sources.xml'
        )
        tree = ElementTree.parse(sources_path)
        entry = tree.getroot().find('entry')
        self._all_children = list(entry) if entry is not None else []
        self._anchor_texts = {
            normalize_anchor(abbr.text): abbr.text
            for abbr in tree.getroot().iter('abbr')
            if abbr.text
        }

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

    def _rebuild_content(self, **kwargs):
        self._ensure_loaded()
        self.content = build_filtered_html(self._all_children, self._collapsed_sections, **kwargs)
        self.viewer.setHtml(self.content)

    def _show_panel(self):
        self.container.show()
        self._update_floating_button_inset()

    def show_panel(self):
        self._show_panel()

    def _anchor_position(self, anchor):
        document = self.viewer.document()
        block = document.begin()
        while block.isValid():
            iterator = block.begin()
            while not iterator.atEnd():
                fragment = iterator.fragment()
                if fragment.isValid() and anchor in fragment.charFormat().anchorNames():
                    return fragment.position()
                iterator += 1
            block = block.next()
        return -1

    def _restore_anchor(self, anchor, position):
        if not anchor or self._anchor_position(anchor) >= 0:
            return
        cursor = QTextCursor(self.viewer.document())
        cursor.setPosition(position)
        cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, 1)
        anchor_format = cursor.charFormat()
        anchor_format.setAnchor(True)
        anchor_format.setAnchorNames([anchor])
        cursor.mergeCharFormat(anchor_format)

    def _move_marker(self, anchor, previous_anchor=None):
        text = self._anchor_texts.get(anchor)
        if not text:
            return False
        document = self.viewer.document()
        old_marker = document.find(ARROW_MARKER)
        if not old_marker.isNull():
            old_position = old_marker.selectionStart()
            old_marker.removeSelectedText()
            self._restore_anchor(previous_anchor, old_position)
        position = self._anchor_position(anchor)
        if position < 0:
            return False
        selection = QTextCursor(document)
        selection.setPosition(position)
        selection.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, len(text))
        if selection.selectedText() != text:
            return False
        anchor_format = QTextCursor(document)
        anchor_format.setPosition(position)
        anchor_format.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, 1)
        marker_format = anchor_format.charFormat()
        marker_format.setAnchor(True)
        marker_format.setAnchorNames([anchor])
        marker = QTextCursor(document)
        marker.setPosition(position)
        marker.insertText(ARROW_MARKER, marker_format)
        return True

    def _capture_view_state(self):
        return (self.main_window.entry_viewer.get_viewer().hasFocus(),
                self.viewer.verticalScrollBar().value())

    def _restore_view_state(self, old_focus, current_scroll):
        self.viewer.verticalScrollBar().setValue(current_scroll)
        if old_focus:
            self.main_window.entry_viewer.get_viewer().setFocus()

    def _expand_matching_sections(self, predicate):
        expanded = False
        for child in self._all_children:
            if child.tag == 'section' and child.get('id') in self._collapsed_sections:
                if predicate(child):
                    self._collapsed_sections.discard(child.get('id'))
                    expanded = True
        return expanded

    def _section_has_anchor(self, section, anchor):
        return any(anchor == normalize_anchor(abbr.text) for abbr in section.iter('abbr'))

    def _toggle_section(self, section_id):
        self._collapsed_sections ^= {section_id}

        old_focus, current_scroll = self._capture_view_state()

        text = self.search_line.text() if self.search_visible else None
        marker = None if (self.search_visible and text) else self.current_anchor
        self._rebuild_content(search_text=text, marker_anchor=marker)

        self._restore_view_state(old_focus, current_scroll)

    def _on_anchor_clicked(self, url):
        url_str = url.toString()
        prefix = SCHEME_TOGGLE_SECTION + ':'
        if url_str.startswith(prefix):
            section_id = url_str[len(prefix):]
            self._toggle_section(section_id)
        else:
            self.main_window.on_link_clicked(url)

    def scroll_to_source(self, source_abbreviation, was_visible=None):
        self._ensure_loaded()
        was_search = self.search_visible
        if was_search:
            self.close_search_bar()
        else:
            self.search_line.clear()

        if not self.original_content:
            return

        anchor = source_abbreviation.rstrip(':').rstrip('.')

        expanded = self._expand_matching_sections(
            lambda section: self._section_has_anchor(section, anchor))

        previous_anchor = self.current_anchor
        self.current_anchor = anchor
        if was_visible is None:
            was_visible = self.sources_visible

        if was_visible:
            old_focus, current_scroll = self._capture_view_state()

        if was_visible and not was_search and not expanded and self._move_marker(anchor, previous_anchor):
            self.content = build_filtered_html(
                self._all_children, self._collapsed_sections, marker_anchor=anchor)
            self.scroll_manager.scroll_to_anchor(anchor)
            return

        updates_enabled = self.viewer.updatesEnabled()
        self.viewer.setUpdatesEnabled(False)
        try:
            self._rebuild_content(marker_anchor=anchor)

            if not was_visible:
                self._show_panel()
                self.sources_visible = True
            else:
                self._restore_view_state(old_focus, current_scroll)

            QApplication.processEvents()
            self.scroll_manager.scroll_to_anchor(anchor)
        finally:
            self.viewer.setUpdatesEnabled(updates_enabled)

    def _on_search(self, text):
        self._ensure_loaded()
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
            self._expand_matching_sections(
                lambda section: section_matches(section, pattern))

            self._rebuild_content(search_text=text)

    def toggle(self):
        self._ensure_loaded()
        self.sources_visible = not self.sources_visible
        if self.sources_visible:
            if self.content:
                self.viewer.setHtml(self.content)
                QApplication.processEvents()
                if self.current_anchor:
                    self.scroll_manager.scroll_to_anchor(self.current_anchor)
            self._show_panel()
        else:
            self.container.hide()
            self.content = self.original_content
            self._collapsed_sections.clear()
            self.current_anchor = None
            self.scroll_manager.last_anchor = None
            if self.search_visible:
                self.close_search_bar()
        return self.sources_visible

    def _update_floating_button_inset(self, *args):
        inset = overlay_right_inset(self.viewer_wrapper, self.viewer)
        self._overlay_layout.setColumnMinimumWidth(1, inset)

    def handle_resize(self):
        self.scroll_manager.handle_resize()

    def get_widget(self):
        return self.container