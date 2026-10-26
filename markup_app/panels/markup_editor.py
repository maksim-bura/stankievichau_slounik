import xml.etree.ElementTree as ElementTree

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QTabWidget, QPushButton, QGridLayout
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QTextCursor, QTextCharFormat

from dictionary_app.format.format_entry import format_entry
from dictionary_app.widgets.dict_text_browser import NoBlueFocusFrameStyle
from dictionary_app.theme.styles import ENTRY_STYLESHEET
from dictionary_app.theme.layout_constants import LAYOUT_MARGINS, LAYOUT_SPACING, BUTTON_SIZE
from markup_app.theme.layout_constants import (
    EDITOR_TOOLBAR_MARGINS, EDITOR_TOOLBAR_SPACING, EDITOR_TOOLBAR_GAP
)
from markup_app.theme.styles import ENTRY_CHECKED_TOGGLE_STYLE
from markup_app.utils.constants import FLOPPY_MARKER
from markup_app.localization import strings
from markup_app.panels.tag_button import TagButton, UniformTabBar
from markup_app.panels.xml_text_edit import XmlTextEdit, strip_link_markers
from dictionary_app.utils.normalize_headword import resolve_headword
from dictionary_app.utils.measure_scrollbars import overlay_right_inset
from dictionary_app.utils.constants import CHECK_BLANK


TAG_BUTTON_GROUPS = [
    ['d', 'hw', 'n', 'g', 'sense', 't', 'ex', 'st', 'src', 'see', 'lang'],
    ['br'],
    ['p', 'i', 'b'],
]


class EditorPane(QWidget):
    content_changed = Signal()
    link_marks_stale = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_modified = False
        self._baseline = ''
        self._overlay_layout = None

        layout = QVBoxLayout()
        layout.setContentsMargins(*LAYOUT_MARGINS)
        layout.setSpacing(LAYOUT_SPACING)

        self._tabs = QTabWidget()
        self._tabs.setTabPosition(QTabWidget.South)
        uniform_bar = UniformTabBar()
        uniform_bar.setExpanding(False)
        self._tabs.setTabBar(uniform_bar)
        self._tabs.currentChanged.connect(self._on_tab_changed)

        self._text_edit = XmlTextEdit()
        self._text_edit.setReadOnly(False)
        self._text_edit.textChanged.connect(self._on_text_changed)
        self._text_edit.link_marks_stale.connect(self.link_marks_stale)

        self._author_edit = QTextEdit()
        self._author_edit.setReadOnly(True)
        self._author_edit.document().setDefaultStyleSheet(ENTRY_STYLESHEET)
        self._author_edit.setStyle(NoBlueFocusFrameStyle(self._author_edit.style()))

        self._tabs.addTab(self._text_edit, strings.tabs.xml)
        self._tabs.addTab(self._author_edit, strings.tabs.ui)

        self.checked_toggle = QPushButton(CHECK_BLANK)
        self.checked_toggle.setFixedSize(BUTTON_SIZE)
        self.checked_toggle.setCheckable(True)
        self.checked_toggle.setCursor(Qt.PointingHandCursor)
        self.checked_toggle.setStyleSheet(ENTRY_CHECKED_TOGGLE_STYLE)
        self.checked_toggle.hide()

        self.save_button = QPushButton(FLOPPY_MARKER)
        self.save_button.setFixedSize(BUTTON_SIZE)
        self.save_button.setCursor(Qt.PointingHandCursor)
        self.save_button.setStyleSheet(ENTRY_CHECKED_TOGGLE_STYLE)
        self.save_button.hide()

        overlay = QWidget()
        overlay_layout = QHBoxLayout()
        overlay_layout.setContentsMargins(0, 0, 0, 0)
        overlay_layout.setSpacing(0)
        overlay_layout.addWidget(self.checked_toggle)
        overlay_layout.addWidget(self.save_button)
        overlay.setLayout(overlay_layout)

        entry_wrapper = QWidget()
        wrapper_layout = QGridLayout()
        wrapper_layout.setContentsMargins(0, 0, 0, 0)
        wrapper_layout.setSpacing(0)
        wrapper_layout.addWidget(self._tabs, 0, 0, 1, 2)
        wrapper_layout.setColumnStretch(0, 1)
        wrapper_layout.setColumnStretch(1, 0)
        wrapper_layout.setColumnMinimumWidth(1, 0)
        wrapper_layout.addWidget(
            overlay, 0, 0, alignment=Qt.AlignTop | Qt.AlignRight
        )
        entry_wrapper.setLayout(wrapper_layout)

        layout.addWidget(entry_wrapper)
        self.setLayout(layout)

        self._overlay_layout = wrapper_layout
        self._entry_wrapper = entry_wrapper
        self._text_edit.verticalScrollBar().rangeChanged.connect(self._update_overlay_inset)
        self._author_edit.verticalScrollBar().rangeChanged.connect(self._update_overlay_inset)

    def set_entry(self, xml_text):
        self._is_modified = False
        self._text_edit.blockSignals(True)
        self._text_edit.setCurrentCharFormat(QTextCharFormat())
        self._text_edit.setPlainText(xml_text)
        self._text_edit.blockSignals(False)
        self._baseline = self.get_xml()
        self._text_edit.reset_state()
        self._text_edit.setExtraSelections([])
        self._render_author()

    def mark_sub_hw(self, headword, occurrence_index=0, keep_acc=0, separate_occurrences=False):
        if not headword:
            return
        norm = resolve_headword(headword.strip(), keep_acc)
        self._text_edit.mark_sub_hw(norm, occurrence_index, separate_occurrences)

    def mark_main_non_d(self, headword, occurrence_index=0, keep_acc=0):
        if not headword:
            return
        norm = resolve_headword(headword.strip(), keep_acc)
        self._text_edit.mark_main_non_d(norm, occurrence_index)

    def highlight_broken_links(self, spans):
        self._text_edit._broken_link_spans = list(spans)
        self._text_edit._refresh_selections()

    def highlight_grammar_marks(self, g_spans, hw_spans):
        self._text_edit._grammar_g_spans = list(g_spans)
        self._text_edit._grammar_hw_spans = list(hw_spans)
        self._text_edit._refresh_selections()

    def clear_grammar_marks(self):
        if not self._text_edit._grammar_g_spans and not self._text_edit._grammar_hw_spans:
            return
        self._text_edit._grammar_g_spans = []
        self._text_edit._grammar_hw_spans = []
        self._text_edit._refresh_selections()

    def get_xml(self):
        return strip_link_markers(self._text_edit.toPlainText())

    def is_modified(self):
        return self._is_modified

    def mark_saved(self):
        self._is_modified = False
        self._baseline = self.get_xml()
        self._text_edit.document().clearUndoRedoStacks()
        self._text_edit._pair_delete_snapshot = None
        self._text_edit._last_deleted_open = None
        self._text_edit._last_deleted_close = None
        self._text_edit._last_deleted_forward = None

    def set_link_marks(self, offsets, tooltips=None, reset_undo=False):
        self._text_edit.set_link_marks(offsets, tooltips, reset_undo)

    def _render_author(self):
        xml = self.get_xml()
        try:
            root = ElementTree.fromstring(xml)
            html = format_entry(xml)
            self._author_edit.blockSignals(True)
            self._author_edit.setHtml(html)
            self._author_edit.blockSignals(False)
        except ElementTree.ParseError:
            self._author_edit.blockSignals(True)
            self._author_edit.setPlainText(xml)
            self._author_edit.blockSignals(False)

    def _on_tab_changed(self, index):
        if index == 1:
            self._render_author()
        self._update_overlay_inset()

    def _update_overlay_inset(self, *args):
        if self._overlay_layout is None:
            return
        widget = self._tabs.currentWidget()
        inset = 0
        if widget is not None:
            inset = overlay_right_inset(self._entry_wrapper, widget)
        self._overlay_layout.setColumnMinimumWidth(1, inset)

    def _on_text_changed(self):
        self._is_modified = self.get_xml() != self._baseline
        self.content_changed.emit()

    def insert_tag(self, tag_name):
        cursor = self._text_edit.textCursor()
        cursor.beginEditBlock()
        try:
            if tag_name == 'br':
                cursor.insertText('<br />')
                self._text_edit.setTextCursor(cursor)
                return

            if tag_name == 'sense':
                selected = cursor.selectedText()
                if selected:
                    cursor.insertText(f'<sense n="">{selected}</sense>')
                else:
                    cursor.insertText('<sense n=""></sense>')
                    caret = cursor.position() - len('</sense>') - len('">')
                    cursor.setPosition(caret)
                    self._text_edit.setTextCursor(cursor)
                return

            if tag_name == 'lang':
                selected = cursor.selectedText()
                if selected:
                    cursor.insertText(f'<lang code="">{selected}</lang>')
                else:
                    cursor.insertText('<lang code=""></lang>')
                    caret = cursor.position() - len('</lang>') - len('">')
                    cursor.setPosition(caret)
                    self._text_edit.setTextCursor(cursor)
                return

            selected = cursor.selectedText()
            if selected:
                replacement = f'<{tag_name}>{selected}</{tag_name}>'
                cursor.insertText(replacement)
                return

            open_len = len(tag_name) + 2
            cursor.insertText(f'<{tag_name}></{tag_name}>')
            cursor.movePosition(
                QTextCursor.MoveOperation.Left,
                QTextCursor.MoveMode.MoveAnchor,
                cursor.position() - open_len,
            )
            self._text_edit.setTextCursor(cursor)
        finally:
            cursor.endEditBlock()


class MarkupEditor(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout()
        layout.setContentsMargins(*LAYOUT_MARGINS)
        layout.setSpacing(LAYOUT_SPACING)

        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(*EDITOR_TOOLBAR_MARGINS)
        toolbar.setSpacing(EDITOR_TOOLBAR_SPACING)

        for group_idx, group in enumerate(TAG_BUTTON_GROUPS):
            if group_idx:
                toolbar.addSpacing(EDITOR_TOOLBAR_GAP)
            for tag_name in group:
                btn = TagButton(tag_name, tag_name)
                btn.clicked_with_tag.connect(self._on_tag_clicked)
                toolbar.addWidget(btn)

        toolbar.addStretch()

        layout.addLayout(toolbar)
        self.pane = EditorPane()
        self.checked_toggle = self.pane.checked_toggle
        self.save_button = self.pane.save_button

        layout.addWidget(self.pane)

        self.setLayout(layout)

    def _on_tag_clicked(self, tag_name):
        self.pane.insert_tag(tag_name)
