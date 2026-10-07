import re
import xml.etree.ElementTree as ElementTree
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit,
    QTabWidget, QTabBar, QPushButton
)
from PySide6.QtCore import Qt, Signal, QTimer, QSize
from PySide6.QtGui import QTextCursor, QTextCharFormat, QColor
from format.entry_formatter import format_entry
from theme.widget_styles import ENTRY_STYLESHEET, COLOR_HIGHLIGHT_BG, FONT_STACK
from theme.layout_constants import (
    EDITOR_TOOLBAR_MARGINS, EDITOR_TOOLBAR_SPACING,
    LAYOUT_MARGINS, LAYOUT_SPACING
)
from markup.styles import TAG_BUTTON_STYLE
from localization import strings
from app.widgets.dict_text_browser import NoBlueFocusFrameStyle


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
_NAME_CHAR_RE = re.compile(r'[A-Za-z0-9_]')


def _is_name_char(ch):
    return len(ch) == 1 and _NAME_CHAR_RE.fullmatch(ch) is not None


def _scan_tags(text):
    tags = []
    i = 0
    n = len(text)
    while i < n:
        lt = text.find('<', i)
        if lt < 0:
            break
        gt = text.find('>', lt + 1)
        if gt < 0:
            break
        closing = text[lt + 1:lt + 2] == '/'
        ns = lt + (2 if closing else 1)
        ne = ns
        while ne < gt and _is_name_char(text[ne]):
            ne += 1
        inner = text[lt + 1:gt]
        if ne == ns and inner not in ('', '/'):
            i = lt + 1
            continue
        tags.append({
            'start': lt,
            'end': gt + 1,
            'name_start': ns,
            'name_end': ne,
            'closing': closing,
            'self_closing': (not closing) and inner.rstrip().endswith('/'),
            'name': text[ns:ne],
        })
        i = gt + 1
    return tags


def _partner_tag(tags, edited):
    stack = []
    for tag in tags:
        if tag['self_closing']:
            continue
        if tag['closing']:
            for j in range(len(stack) - 1, -1, -1):
                if stack[j]['name'] == tag['name']:
                    open_tag = stack.pop(j)
                    if open_tag is edited:
                        return tag
                    if tag is edited:
                        return open_tag
                    break
        else:
            stack.append(tag)
    return None


def _build_tag_dicts(text):
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
    return tags


def _find_tag_pair_at_boundary(text, char_pos):
    tags = _build_tag_dicts(text)

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
                if char_pos == tag['start'] or char_pos == tag['end'] - 1:
                    return tag, tag
        else:
            if tag['self_closing'] and (
                char_pos == tag['start'] or char_pos == tag['end'] - 1
            ):
                return tag, tag
            stack.append(tag)
    for open_tag in stack:
        if open_tag['self_closing']:
            continue
        if char_pos == open_tag['start'] or char_pos == open_tag['end'] - 1:
            return open_tag, open_tag
    return None, None


def _find_rogue_tags(text):
    tags = _build_tag_dicts(text)
    stack = []
    rogues = []
    for tag in tags:
        if tag['self_closing']:
            continue
        if tag['closing']:
            for i in range(len(stack) - 1, -1, -1):
                if stack[i]['name'] == tag['name']:
                    stack.pop(i)
                    break
            else:
                rogues.append(tag)
        else:
            stack.append(tag)
    rogues.extend(stack)
    return rogues


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


class _UniformTabBar(QTabBar):
    def tabSizeHint(self, index):
        hint = super().tabSizeHint(index)
        widths = [super().tabSizeHint(i).width() for i in range(self.count())]
        return QSize(max(widths), hint.height()) if widths else hint


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
        self._baseline = ''

        layout = QVBoxLayout()
        layout.setContentsMargins(*LAYOUT_MARGINS)
        layout.setSpacing(LAYOUT_SPACING)

        self._tabs = QTabWidget()
        self._tabs.setTabPosition(QTabWidget.South)
        uniform_bar = _UniformTabBar()
        uniform_bar.setExpanding(False)
        self._tabs.setTabBar(uniform_bar)
        self._tabs.currentChanged.connect(self._on_tab_changed)

        self._text_edit = _TagAwareTextEdit()
        self._text_edit.setReadOnly(False)
        self._text_edit.textChanged.connect(self._on_text_changed)

        self._author_edit = QTextEdit()
        self._author_edit.setReadOnly(True)
        self._author_edit.document().setDefaultStyleSheet(ENTRY_STYLESHEET)
        self._author_edit.setStyle(NoBlueFocusFrameStyle(self._author_edit.style()))

        self._tabs.addTab(self._text_edit, strings.markup.tabs.text)
        self._tabs.addTab(self._author_edit, strings.markup.tabs.author)

        layout.addWidget(self._tabs)
        self.setLayout(layout)

    def set_entry(self, entry_id, xml_text):
        self._entry_id = entry_id
        self._xml_text = xml_text
        self._is_modified = False
        self._text_edit.blockSignals(True)
        self._text_edit.setPlainText(xml_text)
        self._text_edit.blockSignals(False)
        self._baseline = self._text_edit.toPlainText()
        self._text_edit._pending_tag_delete = False
        self._text_edit._pending_delete_forward = None
        self._text_edit._pair_delete_snapshot = None
        self._text_edit._last_deleted_open = None
        self._text_edit._last_deleted_close = None
        self._text_edit._last_deleted_forward = None
        self._text_edit._rogue_tags = []
        self._text_edit.setExtraSelections([])
        self._render_author()

    def get_xml(self):
        return self._text_edit.toPlainText()

    def is_modified(self):
        return self._is_modified

    def mark_saved(self):
        self._is_modified = False
        self._baseline = self._text_edit.toPlainText()
        self._text_edit.document().clearUndoRedoStacks()
        self._text_edit._pair_delete_snapshot = None
        self._text_edit._last_deleted_open = None
        self._text_edit._last_deleted_close = None
        self._text_edit._last_deleted_forward = None

    def clear(self):
        self._entry_id = None
        self._xml_text = ''
        self._is_modified = False
        self._baseline = ''
        self._text_edit.blockSignals(True)
        self._text_edit.clear()
        self._text_edit.blockSignals(False)
        self._text_edit._rogue_tags = []
        self._text_edit.setExtraSelections([])
        self._text_edit._pending_tag_delete = False
        self._text_edit._pending_open_tag = None
        self._text_edit._pending_close_tag = None
        self._text_edit._pending_delete_forward = None
        self._text_edit._pair_delete_snapshot = None
        self._text_edit._last_deleted_open = None
        self._text_edit._last_deleted_close = None
        self._text_edit._last_deleted_forward = None
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
        self._is_modified = self._text_edit.toPlainText() != self._baseline
        self.content_changed.emit()

    def insert_tag(self, tag_name):
        cursor = self._text_edit.textCursor()
        cursor.beginEditBlock()
        try:
            if tag_name == 'br':
                cursor.insertText('<br />')
                self._text_edit.setTextCursor(cursor)
                return

            selected = cursor.selectedText()
            if selected:
                replacement = f'<{tag_name}>{selected}</{tag_name}>'
                cursor.insertText(replacement)
            else:
                cursor.insertText(f'<{tag_name}></{tag_name}>')
                cursor.movePosition(QTextCursor.MoveOperation.Left, QTextCursor.MoveMode.MoveAnchor, len(tag_name) + 2)
                self._text_edit.setTextCursor(cursor)
        finally:
            cursor.endEditBlock()


class _TagAwareTextEdit(QTextEdit):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setStyle(NoBlueFocusFrameStyle(self.style()))
        self.setStyleSheet(f'font-family: {FONT_STACK}; font-size: 12pt;')
        self.setAcceptRichText(False)
        self._pending_tag_delete = False
        self._pending_open_tag = None
        self._pending_close_tag = None
        self._pending_delete_forward = None
        self._pair_delete_snapshot = None
        self._last_deleted_open = None
        self._last_deleted_close = None
        self._last_deleted_forward = None
        self._rogue_tags = []
        self.cursorPositionChanged.connect(self._reset_pending_tag_delete)
        self.textChanged.connect(self._check_pair_restore)
        self.textChanged.connect(self._schedule_rogue_scan)

    def _reset_pending_tag_delete(self):
        self.setExtraSelections([])
        self._rogue_tags = []
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
            cursor = self.textCursor()
            cursor.beginEditBlock()
            try:
                self.insertPlainText(text)
            finally:
                cursor.endEditBlock()

    def _build_pair_selections(self, open_tag, close_tag):
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

        return [sel_open, sel_close]

    def _build_rogue_selections(self):
        fmt = QTextCharFormat()
        fmt.setBackground(QColor(COLOR_HIGHLIGHT_BG))
        sels = []
        for tag in self._rogue_tags:
            sel = QTextEdit.ExtraSelection()
            sel.format = fmt
            sel.cursor = self.textCursor()
            sel.cursor.setPosition(tag['start'])
            sel.cursor.setPosition(tag['end'], QTextCursor.KeepAnchor)
            sels.append(sel)
        return sels

    def _highlight_tag_pair(self, open_tag, close_tag):
        self.setExtraSelections(
            self._build_pair_selections(open_tag, close_tag)
            + self._build_rogue_selections()
        )

    def _schedule_rogue_scan(self):
        QTimer.singleShot(0, self._rescan_rogues)

    def _rescan_rogues(self):
        self._rogue_tags = _find_rogue_tags(self.toPlainText())
        if (
            self._pending_tag_delete
            and self._pending_open_tag
            and self._pending_close_tag
        ):
            self._highlight_tag_pair(
                self._pending_open_tag, self._pending_close_tag
            )
        else:
            self.setExtraSelections(self._build_rogue_selections())

    def _try_synced_name_insert(self, event):
        if event.modifiers() & (Qt.ControlModifier | Qt.MetaModifier):
            return False
        text = self.toPlainText()
        cursor = self.textCursor()
        tags = _scan_tags(text)

        if cursor.hasSelection():
            sel_a = cursor.selectionStart()
            sel_b = cursor.selectionEnd()
            tag = next(
                (t for t in tags if t['start'] <= sel_a and sel_b <= t['end']),
                None,
            )
            if (
                not tag or tag['self_closing']
                or sel_a < tag['name_start']
                or sel_b > tag['name_end']
            ):
                return False
            typed = event.text()
            if not typed or not all(_is_name_char(c) for c in typed):
                return False
            name = tag['name']
            rel_a = sel_a - tag['name_start']
            new_name = name[:rel_a] + typed + name[rel_a + (sel_b - sel_a):]
            partner = _partner_tag(tags, tag)
            if not partner:
                return False
            self._apply_synced_name(new_name, tag, partner,
                                    caret_after_main=sel_a + len(typed))
            return True

        pos = cursor.position()
        tag = next(
            (t for t in tags if t['start'] <= pos <= t['end']),
            None,
        )
        if not tag or tag['self_closing']:
            return False
        ch = event.text()
        if len(ch) != 1 or not _is_name_char(ch):
            return False
        name = tag['name']
        rel = pos - tag['name_start']
        if rel < 0 or rel > len(name):
            return False
        new_name = name[:rel] + ch + name[rel:]
        partner = _partner_tag(tags, tag)
        if not partner:
            return False
        self._apply_synced_name(
            new_name, tag, partner, caret_after_main=pos + 1
        )
        return True

    def _try_synced_name_delete(self, event, text, pos, forward):
        if event.modifiers() & (Qt.ControlModifier | Qt.MetaModifier):
            return False
        tags = _scan_tags(text)
        tag = next(
            (t for t in tags if t['start'] < pos < t['end']),
            None,
        )
        if not tag or tag['self_closing']:
            return False
        rm_idx = pos if forward else pos - 1
        if not _is_name_char(text[rm_idx]):
            return False
        name = tag['name']
        rel = rm_idx - tag['name_start']
        if rel < 0 or rel >= len(name):
            return False
        edited = tag
        partner = _partner_tag(tags, tag)
        if not partner:
            return False
        new_name = name[:rel] + name[rel + 1:]
        self._apply_synced_name(
            new_name, edited, partner,
            caret_after_main=pos - (0 if forward else 1),
        )
        return True

    def _apply_synced_name(self, new_name, edited, partner, caret_after_main):
        net = len(new_name) - len(edited['name'])
        if partner['start'] >= edited['end']:
            p_ns = partner['name_start'] + net
        else:
            p_ns = partner['name_start']

        cursor = self.textCursor()
        cursor.beginEditBlock()
        cursor.setPosition(edited['name_start'])
        cursor.setPosition(edited['name_end'], QTextCursor.KeepAnchor)
        cursor.insertText(new_name)
        cursor.setPosition(p_ns)
        cursor.setPosition(p_ns + len(partner['name']), QTextCursor.KeepAnchor)
        cursor.insertText(new_name)
        cursor.endEditBlock()

        if p_ns < caret_after_main:
            caret_after_main += net
        c2 = self.textCursor()
        c2.setPosition(caret_after_main)
        self.setTextCursor(c2)

    def keyPressEvent(self, event):
        if (event.modifiers() & Qt.ControlModifier
                and event.key() in (Qt.Key_Z, Qt.Key_Y)):
            super().keyPressEvent(event)
            return
        cursor = self.textCursor()
        cursor.beginEditBlock()
        try:
            self._handle_key(event)
        finally:
            cursor.endEditBlock()

    def _handle_key(self, event):
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
                if self._try_synced_name_delete(event, text, pos, deleting_forward):
                    return
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
            if self._try_synced_name_insert(event):
                return

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
