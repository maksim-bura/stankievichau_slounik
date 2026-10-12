import re
import xml.etree.ElementTree as ElementTree
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit,
    QTabWidget, QTabBar, QPushButton, QGridLayout, QToolTip,
    QListWidget, QListWidgetItem, QApplication
)
from PySide6.QtCore import Qt, Signal, QTimer, QSize, QRect
from PySide6.QtGui import (
    QTextCursor, QTextCharFormat, QColor, QPainter, QFont, QPen, QFontMetricsF, QPalette,
)
from format.entry_formatter import format_entry
from theme.widget_styles import (
    ENTRY_STYLESHEET, COLOR_HIGHLIGHT_BG, FONT_STACK
)
from theme.layout_constants import LAYOUT_MARGINS, LAYOUT_SPACING, BUTTON_SIZE
from markup.theme.widget_styles import (
    COLOR_D_SPAN_UNDERLINE,
    COLOR_AMBIGUOUS_G_BG,
    COLOR_AMBIGUOUS_HW_BG,
)
from markup.theme.layout_constants import (
    EDITOR_TOOLBAR_MARGINS, EDITOR_TOOLBAR_SPACING,
    EDITOR_TOOLBAR_GAP, EDITOR_TOOLBAR_GAP_LARGE,
)
from markup.theme.styles import TAG_BUTTON_STYLE, ENTRY_CHECKED_TOGGLE_STYLE, ATTRIBUTE_POPUP_STYLE
from markup.utils.constants import FLOPPY_MARKER
from markup.services.attribute_completion import (
    BOOL as _ATTR_BOOL,
    detect_context as _detect_completion_context,
)
from markup.localization import strings
from app.widgets.dict_text_browser import NoBlueFocusFrameStyle
from utils.text_utils import remove_accents, normalize_jo_to_je
from utils.scroll_bar_utility import overlay_right_inset
from utils.constants import CHECK_MARK, CHECK_BLANK
from html import unescape


LINK_MARKER = '\U0001F517'
_LINK_MARK_COLOR = QColor(70, 130, 180)


TAG_BUTTON_GROUPS = [
    ['d', 'hw', 'n', 'g', 'sense', 't', 'ex', 'st', 'src', 'see', 'lang'],
    ['br'],
    ['p', 'i', 'b'],
]
TAG_BUTTON_GROUP_GAPS = [
    EDITOR_TOOLBAR_GAP,
    EDITOR_TOOLBAR_GAP_LARGE,
]

_TAG_RE = re.compile(r'<(/?)(\w+)[^>]*>')
_ENTRY_OPEN_RE = re.compile(r'<entry\b[^>]*>')
_ENTRY_CLOSE_RE = re.compile(r'</entry\s*>')
_HW_TEXT_RE = re.compile(r'<hw\b[^>]*>(.*?)</hw>', re.DOTALL)
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


def _innermost_d_span(text, pos):
    tags = _build_tag_dicts(text)
    stack = []
    for tag in tags:
        if tag['self_closing']:
            continue
        if tag['closing']:
            for i in range(len(stack) - 1, -1, -1):
                if stack[i]['name'] == tag['name']:
                    open_tag = stack.pop(i)
                    if open_tag['name'] == 'd' and open_tag['start'] <= pos <= tag['end']:
                        return open_tag, tag
                    break
        else:
            stack.append(tag)
    return None, None


def _find_hw_occurrence(text, headword_norm, occurrence_index):
    found = None
    k = 0
    for m in _HW_TEXT_RE.finditer(text):
        inner = re.sub(r'<[^>]+>', '', m.group(1)).strip()
        if normalize_jo_to_je(remove_accents(inner)) == headword_norm:
            if k == occurrence_index:
                return m
            found = m
            k += 1
    return found


def _entry_block_span(text):
    m_open = re.search(r'<entry\b[^>]*>', text)
    m_close = re.search(r'</entry>', text)
    if m_open and m_close and m_close.start() > m_open.start():
        return m_open.start(), m_close.end()
    return None


def _non_d_region_hw_count(text, pos):
    entry = _entry_block_span(text) or (0, len(text))
    tags = _build_tag_dicts(text)
    stack = []
    spans = []
    for tag in tags:
        if tag['self_closing']:
            continue
        if tag['closing']:
            for i in range(len(stack) - 1, -1, -1):
                if stack[i]['name'] == tag['name']:
                    open_tag = stack.pop(i)
                    if open_tag['name'] == 'd':
                        spans.append((open_tag['start'], tag['end']))
                    break
        else:
            stack.append(tag)
    a, b = entry
    for s, e in spans:
        if e <= pos and e > a:
            a = e
        if s >= pos and s < b:
            b = s
    count = 0
    for m in _HW_TEXT_RE.finditer(text):
        if a <= m.start() < b:
            count += 1
    return count


def _non_d_regions(text, entry_start, entry_end):
    tags = _build_tag_dicts(text)
    stack = []
    d_spans = []
    for tag in tags:
        if tag['self_closing']:
            continue
        if tag['closing']:
            for i in range(len(stack) - 1, -1, -1):
                if stack[i]['name'] == tag['name']:
                    open_tag = stack.pop(i)
                    if open_tag['name'] == 'd':
                        d_spans.append((open_tag['start'], tag['end']))
                    break
        else:
            stack.append(tag)
    open_match = _ENTRY_OPEN_RE.match(text, entry_start)
    content_start = open_match.end() if open_match else entry_start
    close_match = _ENTRY_CLOSE_RE.search(text, entry_start, entry_end)
    content_end = close_match.start() if close_match else entry_end
    regions = []
    cursor_pos = entry_start
    for span_start, span_end in sorted(d_spans):
        if span_end <= entry_start or span_start >= entry_end:
            continue
        if span_start > cursor_pos:
            regions.append((cursor_pos, span_start))
        if span_end > cursor_pos:
            cursor_pos = span_end
    if cursor_pos < entry_end:
        regions.append((cursor_pos, entry_end))
    regions = [
        (max(s, content_start), min(e, content_end))
        for s, e in regions
    ]
    return [(s, e) for s, e in regions if e > s]


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
        self._overlay_layout = None

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

        self._tabs.addTab(self._text_edit, strings.tabs.xml)
        self._tabs.addTab(self._author_edit, strings.tabs.author)

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
        self._text_edit._d_span_sel = None
        self._text_edit._non_d_underline = []
        self._text_edit._target_hw = None
        self._text_edit._broken_link_spans = []
        self._text_edit._grammar_g_spans = []
        self._text_edit._grammar_hw_spans = []
        self._text_edit._link_marks = []
        self._text_edit._link_mark_tooltips = {}
        self._text_edit.setExtraSelections([])
        self._render_author()

    def mark_sub_hw(self, headword, occurrence_index=0):
        if not headword:
            return
        norm = normalize_jo_to_je(remove_accents(headword.strip()))
        self._text_edit.mark_sub_hw(norm, occurrence_index)

    def mark_main_non_d(self, headword, occurrence_index=0):
        if not headword:
            return
        norm = normalize_jo_to_je(remove_accents(headword.strip()))
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
        self._text_edit._d_span_sel = None
        self._text_edit._non_d_underline = []
        self._text_edit._target_hw = None
        self._text_edit._broken_link_spans = []
        self._text_edit._grammar_g_spans = []
        self._text_edit._grammar_hw_spans = []
        self._text_edit._link_marks = []
        self._text_edit._link_mark_tooltips = {}
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

    def set_link_marks(self, offsets, tooltips=None):
        self._text_edit.set_link_marks(offsets, tooltips)

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


class AttributePopup(QListWidget):
    MAX_VISIBLE = 8

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.Tool
            | Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setFocusPolicy(Qt.NoFocus)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setUniformItemSizes(True)
        self.setStyleSheet(ATTRIBUTE_POPUP_STYLE)
        palette = self.palette()
        palette.setColor(QPalette.Text, QColor('black'))
        palette.setColor(QPalette.HighlightedText, QColor('black'))
        self.setPalette(palette)


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
        self._d_span_sel = None
        self._non_d_underline = []
        self._target_hw = None
        self._broken_link_spans = []
        self._grammar_g_spans = []
        self._grammar_hw_spans = []
        self._link_marks = []
        self._link_mark_tooltips = {}
        self._hovered_link_mark = None
        self._pending_link_tooltip = None
        self._link_tooltip_timer = QTimer(self)
        self._link_tooltip_timer.setSingleShot(True)
        self._link_tooltip_timer.timeout.connect(self._show_pending_link_tooltip)
        self.setMouseTracking(True)
        self._completion_popup = AttributePopup(self)
        self._completion_popup.hide()
        self._completion_popup.itemClicked.connect(self._accept_completion_item)
        self.cursorPositionChanged.connect(self._reset_pending_tag_delete)
        self.textChanged.connect(self._check_pair_restore)
        self.textChanged.connect(self._schedule_rogue_scan)
        self.textChanged.connect(self._hide_completion)

    def _reset_pending_tag_delete(self):
        if self._pending_tag_delete:
            self._pending_tag_delete = False
            self._pending_open_tag = None
            self._pending_close_tag = None
            self._pending_delete_forward = None
        self._rogue_tags = []
        self._refresh_selections()

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

    def _build_broken_link_selections(self):
        fmt = QTextCharFormat()
        fmt.setBackground(QColor(COLOR_HIGHLIGHT_BG))
        sels = []
        for start, end in self._broken_link_spans:
            sel = QTextEdit.ExtraSelection()
            sel.format = fmt
            sel.cursor = self.textCursor()
            sel.cursor.setPosition(start)
            sel.cursor.setPosition(end, QTextCursor.KeepAnchor)
            sels.append(sel)
        return sels

    def _build_grammar_selections(self):
        sels = []
        for start, end in self._grammar_g_spans:
            fmt = QTextCharFormat()
            fmt.setBackground(QColor(COLOR_AMBIGUOUS_G_BG))
            sel = QTextEdit.ExtraSelection()
            sel.format = fmt
            sel.cursor = self.textCursor()
            sel.cursor.setPosition(start)
            sel.cursor.setPosition(end, QTextCursor.KeepAnchor)
            sels.append(sel)
        for start, end in self._grammar_hw_spans:
            fmt = QTextCharFormat()
            fmt.setBackground(QColor(COLOR_AMBIGUOUS_HW_BG))
            sel = QTextEdit.ExtraSelection()
            sel.format = fmt
            sel.cursor = self.textCursor()
            sel.cursor.setPosition(start)
            sel.cursor.setPosition(end, QTextCursor.KeepAnchor)
            sels.append(sel)
        return sels

    def _highlight_tag_pair(self, open_tag, close_tag):
        self.setExtraSelections(
            self._build_composed_selections((open_tag, close_tag))
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
            self._refresh_selections()

    def _compute_d_span_underline(self):
        if self._non_d_underline or self._target_hw is None:
            return None
        text = self.toPlainText()
        match = _find_hw_occurrence(text, self._target_hw[0], self._target_hw[1])
        if match is None:
            return None
        open_tag, close_tag = _innermost_d_span(text, match.start())
        if open_tag is None:
            if _non_d_region_hw_count(text, match.start()) >= 2:
                return None
            span = _entry_block_span(text)
            if span is None:
                return None
            start, end = span
        else:
            start, end = open_tag['start'], close_tag['end']
        fmt = QTextCharFormat()
        fmt.setFontUnderline(True)
        fmt.setUnderlineColor(QColor(COLOR_D_SPAN_UNDERLINE))
        cursor = self.textCursor()
        cursor.setPosition(start)
        cursor.setPosition(end, QTextCursor.KeepAnchor)
        sel = QTextEdit.ExtraSelection()
        sel.format = fmt
        sel.cursor = cursor
        return sel

    def _build_composed_selections(self, pair=None):
        if self._target_hw is not None:
            self._d_span_sel = self._compute_d_span_underline()
        sels = []
        if pair is not None:
            sels.extend(self._build_pair_selections(pair[0], pair[1]))
        sels.extend(self._build_rogue_selections())
        sels.extend(self._build_broken_link_selections())
        sels.extend(self._build_grammar_selections())
        sels.extend(self._build_non_d_underline_selections())
        if self._d_span_sel is not None:
            sels.append(self._d_span_sel)
        return sels

    def _build_non_d_underline_selections(self):
        fmt = QTextCharFormat()
        fmt.setFontUnderline(True)
        fmt.setUnderlineColor(QColor(COLOR_D_SPAN_UNDERLINE))
        sels = []
        for start, end in self._non_d_underline:
            sel = QTextEdit.ExtraSelection()
            sel.format = fmt
            sel.cursor = self.textCursor()
            sel.cursor.setPosition(start)
            sel.cursor.setPosition(end, QTextCursor.KeepAnchor)
            sels.append(sel)
        return sels

    def _refresh_selections(self):
        self.setExtraSelections(self._build_composed_selections())

    def set_link_marks(self, offsets, tooltips=None):
        QToolTip.hideText()
        self._hovered_link_mark = None
        self._pending_link_tooltip = None
        self._link_tooltip_timer.stop()
        self._link_marks = sorted(set(offsets or ()))
        self._link_mark_tooltips = tooltips or {}
        self._apply_link_gaps()
        self.viewport().update()

    def _link_symbol_font(self):
        font = QFont(self.font())
        font.setFamily('Segoe UI Emoji')
        font.setPointSizeF(max(9.0, self.font().pointSizeF()))
        return font

    def _link_symbol_box(self, start):
        document = self.document()
        length = document.characterCount()
        if start < 0 or start + 1 >= length:
            return None
        char_width = QFontMetricsF(self.font()).horizontalAdvance('<')
        caret0 = QTextCursor(document)
        caret0.setPosition(start)
        caret1 = QTextCursor(document)
        caret1.setPosition(start + 1)
        rect0 = self.cursorRect(caret0)
        rect1 = self.cursorRect(caret1)
        gap = (rect1.left() - rect0.left()) - char_width
        if gap <= 1:
            return None
        return QRect(
            int(rect1.left() - gap), int(rect0.top()),
            int(gap), int(rect0.height()),
        )

    def _link_mark_at(self, point):
        for start in self._link_marks:
            box = self._link_symbol_box(start)
            if box is not None and box.contains(point):
                return start
        return None

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
        start = self._link_mark_at(event.position().toPoint())
        if start is None or start not in self._link_mark_tooltips:
            self._hovered_link_mark = None
            self._pending_link_tooltip = None
            self._link_tooltip_timer.stop()
            QToolTip.hideText()
            return
        if start == self._hovered_link_mark:
            return
        self._hovered_link_mark = start
        self._pending_link_tooltip = (
            self.viewport().mapToGlobal(event.position().toPoint()),
            self._link_mark_tooltips[start],
        )
        self._link_tooltip_timer.start(400)

    def leaveEvent(self, event):
        self._hovered_link_mark = None
        self._pending_link_tooltip = None
        self._link_tooltip_timer.stop()
        QToolTip.hideText()
        super().leaveEvent(event)

    def _show_pending_link_tooltip(self):
        if self._pending_link_tooltip is None:
            return
        pos, text = self._pending_link_tooltip
        QToolTip.showText(pos, self._widen_tooltip_html(text), self)

    def _widen_tooltip_html(self, text):
        metrics = QFontMetricsF(self.font())
        widest = 0.0
        for line in text.split('<br>'):
            plain = unescape(re.sub(r'<[^>]+>', '', line))
            widest = max(widest, metrics.horizontalAdvance(plain))
        width = int(widest * 1.5) + 8
        return (
            f'<table width="{width}" cellpadding="0" cellspacing="0">'
            f'<tr><td>{text}</td></tr></table>'
        )

    def _apply_link_gaps(self):
        document = self.document()
        length = document.characterCount()
        spacing = QFontMetricsF(self._link_symbol_font()).horizontalAdvance(
            LINK_MARKER
        ) + 2
        fmt = QTextCharFormat()
        fmt.setFontLetterSpacingType(QFont.AbsoluteSpacing)
        fmt.setFontLetterSpacing(spacing)
        self.blockSignals(True)
        cursor = QTextCursor(document)
        for start in self._link_marks:
            if start < 0 or start + 1 >= length:
                continue
            cursor.setPosition(start)
            cursor.setPosition(start + 1, QTextCursor.KeepAnchor)
            cursor.mergeCharFormat(fmt)
        self.blockSignals(False)
        document.clearUndoRedoStacks()

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self._link_marks:
            return
        viewport_rect = self.viewport().rect()
        painter = QPainter(self.viewport())
        painter.setFont(self._link_symbol_font())
        painter.setPen(QPen(_LINK_MARK_COLOR))
        for start in self._link_marks:
            box = self._link_symbol_box(start)
            if box is None or not viewport_rect.intersects(box):
                continue
            painter.drawText(box, Qt.AlignCenter, LINK_MARKER)
        painter.end()

    def _scroll_line_to_top(self, pos):
        document = self.document()
        block = document.findBlock(pos)
        if block.isValid():
            layout = document.documentLayout()
            block_rect = layout.blockBoundingRect(block)
            within = pos - block.position()
            chosen = block_rect.top()
            block_layout = block.layout()
            for i in range(block_layout.lineCount()):
                line = block_layout.lineAt(i)
                if line.textStart() <= within <= line.textStart() + line.textLength():
                    chosen = block_rect.top() + line.y()
                    break
            scrollbar = self.verticalScrollBar()
            value = round(chosen)
            scrollbar.setValue(max(scrollbar.minimum(),
                                   min(scrollbar.maximum(), value)))
            self.repaint()

    def mark_sub_hw(self, headword_norm, occurrence_index=0):
        self._target_hw = (headword_norm, occurrence_index)
        self._non_d_underline = []
        text = self.toPlainText()
        match = _find_hw_occurrence(text, headword_norm, occurrence_index)
        if match is not None:
            caret = self.textCursor()
            caret.setPosition(match.start())
            self.setTextCursor(caret)
            self._scroll_line_to_top(match.start())
        self._refresh_selections()
        return self._d_span_sel is not None

    def mark_main_non_d(self, headword_norm, occurrence_index=0):
        self._target_hw = None
        self._d_span_sel = None
        self._non_d_underline = []
        text = self.toPlainText()
        match = _find_hw_occurrence(text, headword_norm, occurrence_index)
        if match is not None:
            open_tag, _close_tag = _innermost_d_span(text, match.start())
            if open_tag is None:
                entry = _entry_block_span(text)
                if entry is not None:
                    a, b = entry
                    if re.search(r'<d\b', text[a:b]):
                        self._target_hw = (headword_norm, occurrence_index)
                        self._non_d_underline = _non_d_regions(text, a, b)
            caret = self.textCursor()
            caret.setPosition(match.start())
            self.setTextCursor(caret)
            self._scroll_line_to_top(match.start())
        self._refresh_selections()
        return bool(self._non_d_underline)

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

    def _handle_completion_key(self, event):
        popup = self._completion_popup
        if not popup.isVisible():
            return False
        key = event.key()
        if key == Qt.Key_Escape:
            self._hide_completion()
            return True
        if key == Qt.Key_Down:
            self._move_completion_selection(1)
            return True
        if key == Qt.Key_Up:
            self._move_completion_selection(-1)
            return True
        if key in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Tab):
            self._accept_completion_current()
            return True
        if key in (Qt.Key_Left, Qt.Key_Right, Qt.Key_Home, Qt.Key_End):
            self._hide_completion()
        return False

    def _refresh_completion(self):
        pos = self.textCursor().position()
        ctx = _detect_completion_context(self.toPlainText(), pos)
        if ctx is None:
            self._hide_completion()
            return
        items = ctx.candidates()
        if not items:
            self._hide_completion()
            return
        self._show_completion(items)

    def _show_completion(self, items):
        popup = self._completion_popup
        popup.clear()
        for name, kind in items:
            item = QListWidgetItem(name)
            item.setData(Qt.UserRole, (name, kind))
            popup.addItem(item)
        popup.setCurrentRow(0)
        self._size_completion_popup(popup)
        self._position_completion_popup(popup)
        if not popup.isVisible():
            popup.show()
        popup.raise_()

    def _size_completion_popup(self, popup):
        metrics = popup.fontMetrics()
        width = 80
        for i in range(popup.count()):
            width = max(width, metrics.horizontalAdvance(popup.item(i).text()) + 28)
        row_h = popup.sizeHintForRow(0) if popup.count() else metrics.height() + 4
        visible = min(popup.count(), AttributePopup.MAX_VISIBLE)
        popup.setFixedWidth(width)
        popup.setFixedHeight(visible * row_h + 2 * popup.frameWidth() + 4)

    def _position_completion_popup(self, popup):
        rect = self.cursorRect()
        global_pos = self.viewport().mapToGlobal(rect.bottomLeft())
        screen = QApplication.screenAt(global_pos) or self.screen()
        avail = screen.availableGeometry()
        x = min(max(global_pos.x(), avail.left()), avail.right() - popup.width())
        y = global_pos.y()
        if y + popup.height() > avail.bottom():
            y = self.viewport().mapToGlobal(rect.topLeft()).y() - popup.height()
        popup.move(x, y)

    def _move_completion_selection(self, delta):
        popup = self._completion_popup
        if popup.count() == 0:
            return
        popup.setCurrentRow((popup.currentRow() + delta) % popup.count())

    def _accept_completion_current(self):
        item = self._completion_popup.currentItem()
        if item is not None:
            self._apply_completion(item.data(Qt.UserRole))

    def _accept_completion_item(self, item):
        if item is not None:
            self._apply_completion(item.data(Qt.UserRole))

    def _apply_completion(self, data):
        if not data:
            return
        name, kind = data
        cursor = self.textCursor()
        ctx = _detect_completion_context(self.toPlainText(), cursor.position())
        if ctx is None:
            self._hide_completion()
            return
        start = cursor.position() - len(ctx.fragment)
        cursor.beginEditBlock()
        if ctx.fragment:
            cursor.setPosition(start)
            cursor.setPosition(start + len(ctx.fragment), QTextCursor.KeepAnchor)
            cursor.removeSelectedText()
        if kind == _ATTR_BOOL:
            cursor.insertText(f'{name}="true"')
        else:
            cursor.insertText(f'{name}=""')
            cursor.setPosition(start + len(name) + 2)
        cursor.endEditBlock()
        self.setTextCursor(cursor)
        self._hide_completion()

    def _hide_completion(self):
        self._completion_popup.hide()

    def keyPressEvent(self, event):
        if self._handle_completion_key(event):
            return
        cursor = self.textCursor()
        cursor.beginEditBlock()
        try:
            self._handle_key(event)
        finally:
            cursor.endEditBlock()
        self._refresh_completion()

    def mousePressEvent(self, event):
        self._hide_completion()
        super().mousePressEvent(event)

    def focusOutEvent(self, event):
        self._hide_completion()
        super().focusOutEvent(event)

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

        for group_idx, group in enumerate(TAG_BUTTON_GROUPS):
            if group_idx:
                toolbar.addSpacing(TAG_BUTTON_GROUP_GAPS[group_idx - 1])
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
