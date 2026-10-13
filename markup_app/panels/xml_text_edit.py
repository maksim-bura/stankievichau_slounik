import re
from html import unescape

from PySide6.QtWidgets import (
    QTextEdit, QListWidget, QListWidgetItem, QApplication, QToolTip
)
from PySide6.QtCore import Qt, QTimer, QRect
from PySide6.QtGui import (
    QTextCursor, QTextCharFormat, QColor, QPainter, QFont, QPen,
    QFontMetricsF, QPalette,
)

from dictionary_app.widgets.dict_text_browser import NoBlueFocusFrameStyle
from markup_app.theme.layout_constants import (
    LINK_TOOLTIP_DELAY_MS, TOOLTIP_WIDTH_FACTOR, TOOLTIP_WIDTH_PAD,
)
from markup_app.theme.styles import ATTRIBUTE_POPUP_STYLE
from markup_app.theme.widget_styles import (
    COLOR_D_SPAN_UNDERLINE, COLOR_AMBIGUOUS_G_BG, COLOR_AMBIGUOUS_HW_BG,
)
from dictionary_app.theme.widget_styles import COLOR_HIGHLIGHT_BG, FONT_STACK
from dictionary_app.utils.xml_schema import BOOL as _ATTR_BOOL
from markup_app.services.attribute_completion import (
    detect_context as _detect_completion_context,
)
from markup_app.panels.xml_editing import (
    entry_block_span, find_hw_occurrence, find_rogue_tags, innermost_d_span,
    is_inside_tag, is_name_char, non_d_region_hw_count, non_d_regions,
    pair_at_deletion_boundary, partner_tag, scan_tags,
)


LINK_MARKER = '\U0001F517'
_LINK_MARK_COLOR = QColor(70, 130, 180)
_PAIR_SELECT_RE = re.compile(r'^(<\w+[^>]*>)(.*)(</\w+>)$')


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


class XmlTextEdit(QTextEdit):
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
        self._rogue_tags = find_rogue_tags(self.toPlainText())
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
        match = find_hw_occurrence(text, self._target_hw[0], self._target_hw[1])
        if match is None:
            return None
        open_tag, close_tag = innermost_d_span(text, match.start())
        if open_tag is None:
            if non_d_region_hw_count(text, match.start()) >= 2:
                return None
            span = entry_block_span(text)
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
        self._link_tooltip_timer.start(LINK_TOOLTIP_DELAY_MS)

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
        width = int(widest * TOOLTIP_WIDTH_FACTOR) + TOOLTIP_WIDTH_PAD
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
        match = find_hw_occurrence(text, headword_norm, occurrence_index)
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
        match = find_hw_occurrence(text, headword_norm, occurrence_index)
        if match is not None:
            open_tag, _close_tag = innermost_d_span(text, match.start())
            if open_tag is None:
                entry = entry_block_span(text)
                if entry is not None:
                    a, b = entry
                    if re.search(r'<d\b', text[a:b]):
                        self._target_hw = (headword_norm, occurrence_index)
                        self._non_d_underline = non_d_regions(text, a, b)
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
        tags = scan_tags(text)

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
            if not typed or not all(is_name_char(c) for c in typed):
                return False
            name = tag['name']
            rel_a = sel_a - tag['name_start']
            new_name = name[:rel_a] + typed + name[rel_a + (sel_b - sel_a):]
            partner = partner_tag(tags, tag)
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
        if len(ch) != 1 or not is_name_char(ch):
            return False
        name = tag['name']
        rel = pos - tag['name_start']
        if rel < 0 or rel > len(name):
            return False
        new_name = name[:rel] + ch + name[rel:]
        partner = partner_tag(tags, tag)
        if not partner:
            return False
        self._apply_synced_name(
            new_name, tag, partner, caret_after_main=pos + 1
        )
        return True

    def _try_synced_name_delete(self, event, text, pos, forward):
        if event.modifiers() & (Qt.ControlModifier | Qt.MetaModifier):
            return False
        tags = scan_tags(text)
        tag = next(
            (t for t in tags if t['start'] < pos < t['end']),
            None,
        )
        if not tag or tag['self_closing']:
            return False
        rm_idx = pos if forward else pos - 1
        if not is_name_char(text[rm_idx]):
            return False
        name = tag['name']
        rel = rm_idx - tag['name_start']
        if rel < 0 or rel >= len(name):
            return False
        edited = tag
        partner = partner_tag(tags, tag)
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

            if is_inside_tag(text, pos):
                if self._try_synced_name_delete(event, text, pos, deleting_forward):
                    return
                super().keyPressEvent(event)
                return

            open_tag, close_tag = pair_at_deletion_boundary(text, pos, forward=deleting_forward)
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
