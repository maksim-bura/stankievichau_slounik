import re
import xml.etree.ElementTree as ElementTree
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit,
    QTabWidget, QPushButton
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QTextCursor, QTextCharFormat, QColor
from format.entry_formatter import format_entry
from theme.widget_styles import ENTRY_STYLESHEET, COLOR_HIGHLIGHT_BG
from theme.layout_constants import (
    EDITOR_TOOLBAR_MARGINS, EDITOR_TOOLBAR_SPACING,
    LAYOUT_MARGINS, LAYOUT_SPACING
)
from markup.styles import TAG_BUTTON_STYLE


TAG_BUTTONS_ROW1 = [
    ('d', 'd'),
    ('hw', 'hw'),
    ('g', 'g'),
    ('t', 't'),
    ('ex', 'ex'),
    ('src', 'src'),
    ('st', 'st'),
    ('br', 'br'),
    ('see', 'see'),
    ('i', 'i'),
]

_TAG_RE = re.compile(r'<(/?)(\w+)[^>]*>')
_PAIR_SELECT_RE = re.compile(r'^(<\w+[^>]*>)(.*)(</\w+>)$')


def _find_tag_pair_at_boundary(text, char_pos):
    tags = []
    for m in _TAG_RE.finditer(text):
        raw = text[m.start():m.end()]
        tags.append({
            'start': m.start(),
            'end': m.end(),
            'name': m.group(2),
            'closing': m.group(1) == '/',
            'self_closing': raw.endswith('/>'),
        })

    stack = []
    for tag in tags:
        if tag['closing']:
            for i in range(len(stack) - 1, -1, -1):
                if stack[i]['name'] == tag['name']:
                    open_tag = stack.pop(i)
                    if _tag_delimiter_at_boundary(open_tag, tag, char_pos):
                        return open_tag, tag
                    break
        else:
            if tag['self_closing'] and (
                char_pos == tag['start'] or char_pos == tag['end'] - 1
            ):
                return tag, tag
            stack.append(tag)
    return None, None


def _tag_delimiter_at_boundary(open_tag, close_tag, char_pos):
    return (
        char_pos == open_tag['start']
        or char_pos == open_tag['end'] - 1
        or char_pos == close_tag['start']
        or char_pos == close_tag['end'] - 1
    )


def _is_inside_tag(text, pos):
    for m in _TAG_RE.finditer(text):
        if m.start() < pos < m.end():
            return True
    return False


def _pair_at_deletion_boundary(text, pos, forward):
    char_pos = pos if forward else pos - 1
    if char_pos < 0 or char_pos >= len(text):
        return None, None
    ch = text[char_pos]
    if ch != '>' and ch != '<':
        return None, None
    return _find_tag_pair_at_boundary(text, char_pos)


class TagButton(QPushButton):
    clicked_with_tag = Signal(str)

    def __init__(self, label, tag_name, parent=None):
        super().__init__(label, parent)
        self._tag_name = tag_name
        self.setCursor(Qt.PointingHandCursor)
        self.setFlat(True)
        self.setStyleSheet(TAG_BUTTON_STYLE)
        self.clicked.connect(lambda: self.clicked_with_tag.emit(self._tag_name))


class EditorPane(QWidget):
    content_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._xml_text = ''
        self._entry_id = None
        self._is_modified = False

        layout = QVBoxLayout()
        layout.setContentsMargins(*LAYOUT_MARGINS)
        layout.setSpacing(LAYOUT_SPACING)

        self._tabs = QTabWidget()
        self._tabs.setTabPosition(QTabWidget.South)
        self._tabs.currentChanged.connect(self._on_tab_changed)

        self._text_edit = _TagAwareTextEdit()
        self._text_edit.setReadOnly(False)
        self._text_edit.textChanged.connect(self._on_text_changed)

        self._author_edit = QTextEdit()
        self._author_edit.setReadOnly(True)
        self._author_edit.document().setDefaultStyleSheet(ENTRY_STYLESHEET)

        self._tabs.addTab(self._text_edit, 'Text')
        self._tabs.addTab(self._author_edit, 'Author')

        layout.addWidget(self._tabs)
        self.setLayout(layout)

    def set_entry(self, entry_id, xml_text):
        self._entry_id = entry_id
        self._xml_text = xml_text
        self._is_modified = False
        self._text_edit.blockSignals(True)
        self._text_edit.setPlainText(xml_text)
        self._text_edit.blockSignals(False)
        self._text_edit._pending_tag_delete = False
        self._text_edit._pending_delete_forward = None
        self._text_edit._pair_delete_snapshot = None
        self._text_edit._last_deleted_open = None
        self._text_edit._last_deleted_close = None
        self._text_edit._last_deleted_forward = None
        self._text_edit.setExtraSelections([])
        self._render_author()

    def get_xml(self):
        return self._text_edit.toPlainText()

    def is_modified(self):
        return self._is_modified

    def mark_saved(self):
        self._is_modified = False

    def clear(self):
        self._entry_id = None
        self._xml_text = ''
        self._is_modified = False
        self._text_edit.blockSignals(True)
        self._text_edit.clear()
        self._text_edit.blockSignals(False)
        self._author_edit.clear()

    def _render_author(self):
        xml = self._text_edit.toPlainText()
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

    def _on_text_changed(self):
        self._is_modified = True
        self.content_changed.emit()

    def insert_tag(self, tag_name):
        if tag_name == 'br':
            cursor = self._text_edit.textCursor()
            cursor.insertText('<br />')
            self._text_edit.setTextCursor(cursor)
            return

        cursor = self._text_edit.textCursor()
        selected = cursor.selectedText()
        if selected:
            replacement = f'<{tag_name}>{selected}</{tag_name}>'
            cursor.insertText(replacement)
        else:
            cursor.insertText(f'<{tag_name}></{tag_name}>')
            cursor.movePosition(QTextCursor.MoveOperation.Left, QTextCursor.MoveMode.MoveAnchor, len(tag_name) + 2)
            self._text_edit.setTextCursor(cursor)


class _TagAwareTextEdit(QTextEdit):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setAcceptRichText(False)
        self._pending_tag_delete = False
        self._pending_open_tag = None
        self._pending_close_tag = None
        self._pending_delete_forward = None
        self._pair_delete_snapshot = None
        self._last_deleted_open = None
        self._last_deleted_close = None
        self._last_deleted_forward = None
        self.cursorPositionChanged.connect(self._reset_pending_tag_delete)
        self.textChanged.connect(self._check_pair_restore)

    def _reset_pending_tag_delete(self):
        self.setExtraSelections([])
        if self._pending_tag_delete:
            self._pending_tag_delete = False
            self._pending_open_tag = None
            self._pending_close_tag = None
            self._pending_delete_forward = None

    def _check_pair_restore(self):
        if self._pair_delete_snapshot is None:
            return
        if self.toPlainText() == self._pair_delete_snapshot:
            snapshot = self._pair_delete_snapshot
            open_tag = self._last_deleted_open
            close_tag = self._last_deleted_close
            forward = self._last_deleted_forward
            self._pair_delete_snapshot = None
            self._last_deleted_open = None
            self._last_deleted_close = None
            self._last_deleted_forward = None
            if open_tag and close_tag:
                QTimer.singleShot(
                    0,
                    lambda t=snapshot, o=dict(open_tag), c=dict(close_tag), f=forward:
                        self._apply_restore_highlight(t, o, c, f),
                )

    def _apply_restore_highlight(self, expected_text, open_tag, close_tag, forward):
        if self.toPlainText() == expected_text:
            self._pending_tag_delete = True
            self._pending_open_tag = open_tag
            self._pending_close_tag = close_tag
            self._pending_delete_forward = forward
            self._highlight_tag_pair(open_tag, close_tag)

    def canInsertFromMimeData(self, source):
        return source.hasText()

    def insertFromMimeData(self, source):
        text = source.text()
        if text:
            self.insertPlainText(text)

    def _highlight_tag_pair(self, open_tag, close_tag):
        fmt = QTextCharFormat()
        fmt.setBackground(QColor(COLOR_HIGHLIGHT_BG))

        sel_open = QTextEdit.ExtraSelection()
        sel_open.format = fmt
        sel_open.cursor = self.textCursor()
        sel_open.cursor.setPosition(open_tag['start'])
        sel_open.cursor.setPosition(open_tag['end'], QTextCursor.KeepAnchor)

        sel_close = QTextEdit.ExtraSelection()
        sel_close.format = fmt
        sel_close.cursor = self.textCursor()
        sel_close.cursor.setPosition(close_tag['start'])
        sel_close.cursor.setPosition(close_tag['end'], QTextCursor.KeepAnchor)

        self.setExtraSelections([sel_open, sel_close])

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Backspace, Qt.Key_Delete):
            deleting_forward = event.key() == Qt.Key_Delete
            cursor = self.textCursor()

            if self._pending_tag_delete and not cursor.hasSelection():
                if self._pending_open_tag and self._pending_close_tag:
                    if self._pending_delete_forward != deleting_forward:
                        self._pending_tag_delete = False
                        self._pending_open_tag = None
                        self._pending_close_tag = None
                        self._pending_delete_forward = None
                        self.setExtraSelections([])
                    else:
                        self.blockSignals(True)
                        open_tag = self._pending_open_tag
                        close_tag = self._pending_close_tag

                        self._pair_delete_snapshot = self.toPlainText()
                        self._last_deleted_open = dict(open_tag)
                        self._last_deleted_close = dict(close_tag)
                        self._last_deleted_forward = deleting_forward

                        cursor.beginEditBlock()
                        if open_tag is close_tag:
                            cursor.setPosition(open_tag['start'])
                            cursor.setPosition(open_tag['end'], QTextCursor.KeepAnchor)
                            cursor.removeSelectedText()
                            cursor.setPosition(open_tag['start'])
                        else:
                            cursor.setPosition(close_tag['start'])
                            cursor.setPosition(close_tag['end'], QTextCursor.KeepAnchor)
                            cursor.removeSelectedText()

                            cursor.setPosition(open_tag['start'])
                            cursor.setPosition(open_tag['end'], QTextCursor.KeepAnchor)
                            cursor.removeSelectedText()

                            cursor.setPosition(open_tag['start'])
                        cursor.endEditBlock()
                        self.setTextCursor(cursor)
                        self.setExtraSelections([])
                        self._pending_tag_delete = False
                        self._pending_open_tag = None
                        self._pending_close_tag = None
                        self._pending_delete_forward = None
                        self.blockSignals(False)
                        self.textChanged.emit()
                        return

            self._pending_tag_delete = False
            self._pending_open_tag = None
            self._pending_close_tag = None
            self.setExtraSelections([])

            if cursor.hasSelection():
                if not deleting_forward:
                    selected = cursor.selectedText()
                    m = _PAIR_SELECT_RE.match(selected)
                    if m:
                        self.blockSignals(True)
                        content = m.group(2)
                        cursor.removeSelectedText()
                        cursor.insertText(content)
                        self.setTextCursor(cursor)
                        self.blockSignals(False)
                        self.textChanged.emit()
                        return
                super().keyPressEvent(event)
                return

            text = self.toPlainText()
            pos = cursor.position()

            if _is_inside_tag(text, pos):
                super().keyPressEvent(event)
                return

            open_tag, close_tag = _pair_at_deletion_boundary(text, pos, forward=deleting_forward)
            if open_tag and close_tag:
                self._pending_tag_delete = True
                self._pending_open_tag = open_tag
                self._pending_close_tag = close_tag
                self._pending_delete_forward = deleting_forward
                self._highlight_tag_pair(open_tag, close_tag)
                return

        else:
            self._pending_tag_delete = False
            self._pending_open_tag = None
            self._pending_close_tag = None
            self._pending_delete_forward = None
            self.setExtraSelections([])

        super().keyPressEvent(event)


class MarkupEditor(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout()
        layout.setContentsMargins(*LAYOUT_MARGINS)
        layout.setSpacing(LAYOUT_SPACING)

        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(*EDITOR_TOOLBAR_MARGINS)
        toolbar.setSpacing(EDITOR_TOOLBAR_SPACING)

        for label, tag_name in TAG_BUTTONS_ROW1:
            btn = TagButton(label, tag_name)
            btn.clicked_with_tag.connect(self._on_tag_clicked)
            toolbar.addWidget(btn)

        toolbar.addStretch()

        layout.addLayout(toolbar)
        self.pane = EditorPane()

        layout.addWidget(self.pane)

        self.setLayout(layout)

    def _on_tag_clicked(self, tag_name):
        self.pane.insert_tag(tag_name)
