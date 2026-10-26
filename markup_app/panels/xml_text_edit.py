import re
from bisect import bisect_left
from html import unescape

from PySide6.QtWidgets import ( QTextEdit, QListWidgetItem, QApplication, QToolTip )
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import ( QTextCursor, QTextCharFormat, QFontMetricsF, )

from dictionary_app.widgets.dict_text_browser import NoBlueFocusFrameStyle
from markup_app.theme.layout_constants import (
    COMPLETION_FRAME_PADDING, COMPLETION_MIN_WIDTH, COMPLETION_ROW_PADDING,
    LINK_TOOLTIP_DELAY_MS, TOOLTIP_WIDTH_FACTOR, TOOLTIP_WIDTH_PAD
)
from markup_app.theme.styles import (
    COLOR_AMBIGUOUS_G_BG, COLOR_AMBIGUOUS_HW_BG, COLOR_D_SPAN_UNDERLINE
)
from dictionary_app.theme.styles import COLOR_HIGHLIGHT_BG, FONT_STACK
from dictionary_app.utils.xml_schema import BOOL as _ATTR_BOOL
from markup_app.panels.attribute_popup import AttributePopup
from markup_app.panels.build_selections import ( background_selections, underline_selections, )
from markup_app.services.completion_context import detect_context as _detect_completion_context
from markup_app.utils.constants import LINK_MARKER, LINK_PLACEHOLDER
from markup_app.services.parse_xml_tags import (
    entry_block_span, find_hw_occurrence, find_hw_occurrences, find_rogue_tags,
    innermost_d_span, is_inside_tag, is_name_char, non_d_region_hw_count, non_d_regions,
    pair_at_deletion_boundary, partner_tag, placeholder_clean_starts, placeholder_positions,
    scan_tags
)


_PAIR_SELECT_RE = re.compile(
    r'^(<' + LINK_MARKER + r'?\w+[^>]*>)(.*)(</\w+>)$'
)


def strip_link_markers(text):
    return text.replace(LINK_MARKER, '')


class XmlTextEdit(QTextEdit):
    link_marks_stale = Signal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setStyle(NoBlueFocusFrameStyle(self.style()))
        self.setStyleSheet(f'font-family: {FONT_STACK}; font-size: 12pt;')
        self.setAcceptRichText(False)
        self._pending_open_tag = None
        self._pending_close_tag = None
        self.reset_state()
        self._last_scan_text = None
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
        self.textChanged.connect(self._on_scan_changed)
        self.textChanged.connect(self._schedule_rogue_scan)
        self.textChanged.connect(self._hide_completion)

    def reset_state(self):
        self._pending_tag_delete = False
        self._pending_delete_forward = None
        self._pair_delete_snapshot = None
        self._last_deleted_open = None
        self._last_deleted_close = None
        self._last_deleted_forward = None
        self._rogue_tags = []
        self._d_span_sels = []
        self._non_d_underline = []
        self._non_d_target = None
        self._target_hw = None
        self._separate_occurrences = False
        self._broken_link_spans = []
        self._grammar_g_spans = []
        self._grammar_hw_spans = []
        self._link_marks = []
        self._link_mark_tooltips = {}
        self._link_mark_texts = set()
        self._emoji_clean_starts = []

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
            text = text.replace(LINK_MARKER, '')
        if text:
            cursor = self.textCursor()
            cursor.beginEditBlock()
            try:
                self.insertPlainText(text)
                self._on_scan_changed()
            finally:
                cursor.endEditBlock()

    def _highlight_tag_pair(self, open_tag, close_tag):
        self.setExtraSelections(
            self._build_composed_selections((open_tag, close_tag))
        )

    def _schedule_rogue_scan(self):
        QTimer.singleShot(0, self._rescan_rogues)

    def _rescan_rogues(self):
        self._rogue_tags = find_rogue_tags(self._scan_text())
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

    def _refresh_non_d_underline(self):
        key, occurrence_index = self._non_d_target
        text = self._scan_text()
        self._non_d_underline = []
        self._target_hw = None
        match = find_hw_occurrence(text, key, occurrence_index)
        if match is None:
            return
        open_tag, _close_tag = innermost_d_span(text, match.start())
        if open_tag is not None:
            return
        entry = entry_block_span(text)
        if entry is None:
            return
        a, b = entry
        if not re.search(r'<d\b', text[a:b]):
            return
        self._target_hw = (key, occurrence_index)
        self._non_d_underline = non_d_regions(text, a, b)

    def _compute_d_span_sels(self):
        if self._non_d_underline or self._target_hw is None:
            return []
        text = self._scan_text()
        key = self._target_hw[0]
        if self._separate_occurrences:
            single = find_hw_occurrence(text, key, self._target_hw[1])
            matches = [single] if single is not None else []
        else:
            matches = find_hw_occurrences(text, key)
        spans = []
        seen = set()
        for match in matches:
            open_tag, close_tag = innermost_d_span(text, match.start())
            if open_tag is None:
                if non_d_region_hw_count(text, match.start()) >= 2:
                    continue
                span = entry_block_span(text)
                if span is None:
                    continue
            else:
                span = (open_tag['start'], close_tag['end'])
            if span in seen:
                continue
            seen.add(span)
            spans.append(span)
        return underline_selections(self, spans, COLOR_D_SPAN_UNDERLINE)

    def _clean_spans(self, spans):
        return [
            (self._clean_to_qt(start), self._clean_to_qt(end))
            for start, end in spans
        ]

    def _build_composed_selections(self, pair=None):
        if self._non_d_target is not None:
            self._refresh_non_d_underline()
        if self._target_hw is not None:
            self._d_span_sels = self._compute_d_span_sels()
        else:
            self._d_span_sels = []
        sels = []
        if pair is not None:
            sels.extend(background_selections(
                self,
                [(pair[0]['start'], pair[0]['end']),
                 (pair[1]['start'], pair[1]['end'])],
                COLOR_HIGHLIGHT_BG,
            ))
        sels.extend(background_selections(
            self,
            [(tag['start'], tag['end']) for tag in self._rogue_tags],
            COLOR_HIGHLIGHT_BG,
        ))
        sels.extend(background_selections(
            self, self._clean_spans(self._broken_link_spans),
            COLOR_HIGHLIGHT_BG,
        ))
        sels.extend(background_selections(
            self, self._clean_spans(self._grammar_g_spans),
            COLOR_AMBIGUOUS_G_BG,
        ))
        sels.extend(background_selections(
            self, self._clean_spans(self._grammar_hw_spans),
            COLOR_AMBIGUOUS_HW_BG,
        ))
        sels.extend(underline_selections(
            self, self._non_d_underline, COLOR_D_SPAN_UNDERLINE,
        ))
        sels.extend(self._d_span_sels)
        return sels

    def _refresh_selections(self):
        self.setExtraSelections(self._build_composed_selections())

    def _scan_text(self):
        return self.toPlainText().replace(LINK_MARKER, LINK_PLACEHOLDER)

    def _clean_to_qt(self, clean_pos):
        return clean_pos + 2 * bisect_left(self._emoji_clean_starts, clean_pos)

    def set_link_marks(self, offsets, tooltips=None, reset_undo=False):
        QToolTip.hideText()
        self._hovered_link_mark = None
        self._pending_link_tooltip = None
        self._link_tooltip_timer.stop()
        desired = sorted(set(offsets or ()))
        tooltips = tooltips or {}
        text = self._scan_text()
        emojis = placeholder_positions(text)
        stray = [p for p in emojis if p == 0 or text[p - 1] != '<']
        if stray:
            self._remove_link_emojis(stray)
            text = self._scan_text()
            emojis = placeholder_positions(text)
        clean_starts = placeholder_clean_starts(emojis)
        desired_set = set(desired)
        doomed = [
            p for i, p in enumerate(emojis)
            if clean_starts[i] not in desired_set
        ]
        if doomed:
            self._remove_link_emojis(doomed)
            text = self._scan_text()
            emojis = placeholder_positions(text)
            clean_starts = placeholder_clean_starts(emojis)
        kept_clean = set(clean_starts)
        clean = text.replace(LINK_PLACEHOLDER, '')
        desired_texts = {}
        for off in desired:
            if off < len(clean) and clean[off] == '<':
                gt = clean.find('>', off)
                if gt != -1:
                    desired_texts[off] = clean[off:gt + 1]
        if reset_undo:
            self._link_mark_texts = set(desired_texts.values())
        new_marks = []
        new_tooltips = {}
        new_emoji_clean = []
        self.blockSignals(True)
        try:
            cursor = QTextCursor(self.document())
            cursor.beginEditBlock()
            for off in desired:
                if off not in desired_texts:
                    continue
                before = sum(1 for co in new_emoji_clean if co < off)
                doc_lt = off + 2 * before
                has_emoji = off in kept_clean
                if not has_emoji:
                    if desired_texts[off] not in self._link_mark_texts:
                        continue
                    cursor.setPosition(doc_lt + 1)
                    cursor.insertText(LINK_MARKER)
                    fmt = QTextCharFormat()
                    fmt.setFontFamily('Segoe UI Emoji')
                    cursor.setPosition(doc_lt + 1)
                    cursor.setPosition(doc_lt + 3, QTextCursor.KeepAnchor)
                    cursor.mergeCharFormat(fmt)
                new_marks.append(doc_lt)
                new_emoji_clean.append(off)
                tip = tooltips.get(off)
                if tip is not None:
                    new_tooltips[doc_lt] = tip
            cursor.endEditBlock()
        finally:
            self.blockSignals(False)
        self._link_marks = new_marks
        self._link_mark_tooltips = new_tooltips
        self._emoji_clean_starts = new_emoji_clean
        if reset_undo:
            self.document().clearUndoRedoStacks()
        self._last_scan_text = self._scan_text()
        self._refresh_selections()
        self.setCurrentCharFormat(QTextCharFormat())
        self.viewport().update()

    def _remove_link_emojis(self, positions):
        self.blockSignals(True)
        try:
            cursor = QTextCursor(self.document())
            cursor.beginEditBlock()
            try:
                for p in sorted(set(positions), reverse=True):
                    cursor.setPosition(p)
                    cursor.setPosition(p + 2, QTextCursor.KeepAnchor)
                    cursor.removeSelectedText()
            finally:
                cursor.endEditBlock()
        finally:
            self.blockSignals(False)

    def _on_scan_changed(self):
        scan = self._scan_text()
        if scan == self._last_scan_text:
            return
        if not self._link_mark_texts and not self._link_marks:
            self._last_scan_text = scan
            return
        self._last_scan_text = scan
        self._enforce_link_marks()
        self.link_marks_stale.emit()
        self._last_scan_text = self._scan_text()

    def _enforce_link_marks(self):
        if not self._link_mark_texts and not self._link_marks:
            return
        text = self._scan_text()
        emojis = placeholder_positions(text)
        bad = []
        for p in emojis:
            if p < 1 or text[p - 1] != '<':
                bad.append(p)
                continue
            gt = text.find('>', p)
            host = text[p - 1:gt + 1] if gt != -1 else None
            if host is None or host.replace(LINK_PLACEHOLDER, '') not in self._link_mark_texts:
                bad.append(p)
        if bad:
            self._remove_link_emojis(bad)
            text = self._scan_text()
            emojis = placeholder_positions(text)
        self._link_marks = [
            p - 1 for p in emojis if p >= 1 and text[p - 1] == '<'
        ]
        self._emoji_clean_starts = placeholder_clean_starts(emojis)
        mark_set = set(self._link_marks)
        self._link_mark_tooltips = {
            k: v for k, v in self._link_mark_tooltips.items()
            if k in mark_set
        }

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
        pos = self.cursorForPosition(event.position().toPoint()).position()
        text = self._scan_text()
        start = None
        if text[pos:pos + 2] == LINK_PLACEHOLDER:
            start = pos - 1
        elif 0 < pos < len(text) and text[pos - 1:pos + 1] == LINK_PLACEHOLDER:
            start = pos - 2
        elif pos >= 2 and text[pos - 2:pos] == LINK_PLACEHOLDER:
            start = pos - 3
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

    def mark_sub_hw(self, headword_norm, occurrence_index=0, separate_occurrences=False):
        self._target_hw = (headword_norm, occurrence_index)
        self._separate_occurrences = separate_occurrences
        self._non_d_underline = []
        self._non_d_target = None
        text = self._scan_text()
        match = find_hw_occurrence(text, headword_norm, occurrence_index)
        if match is not None:
            caret = self.textCursor()
            caret.setPosition(match.start())
            self.setTextCursor(caret)
            self._scroll_line_to_top(match.start())
        self._refresh_selections()
        return bool(self._d_span_sels)

    def mark_main_non_d(self, headword_norm, occurrence_index=0):
        self._target_hw = None
        self._d_span_sels = []
        self._non_d_underline = []
        self._non_d_target = (headword_norm, occurrence_index)
        text = self._scan_text()
        match = find_hw_occurrence(text, headword_norm, occurrence_index)
        if match is not None:
            caret = self.textCursor()
            caret.setPosition(match.start())
            self.setTextCursor(caret)
            self._scroll_line_to_top(match.start())
        self._refresh_selections()
        return bool(self._non_d_underline)

    def _try_synced_name_insert(self, event):
        if event.modifiers() & (Qt.ControlModifier | Qt.MetaModifier):
            return False
        text = self._scan_text()
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
        self.blockSignals(True)
        try:
            cursor.beginEditBlock()
            cursor.setPosition(edited['name_start'])
            cursor.setPosition(edited['name_end'], QTextCursor.KeepAnchor)
            cursor.insertText(new_name)
            cursor.setPosition(p_ns)
            cursor.setPosition(p_ns + len(partner['name']), QTextCursor.KeepAnchor)
            cursor.insertText(new_name)
            cursor.endEditBlock()
        finally:
            self.blockSignals(False)

        if p_ns < caret_after_main:
            caret_after_main += net
        c2 = self.textCursor()
        c2.setPosition(caret_after_main)
        self.setTextCursor(c2)
        self.textChanged.emit()

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
        ctx = _detect_completion_context(self._scan_text(), pos)
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
        width = COMPLETION_MIN_WIDTH
        if popup.count():
            popup.setUniformItemSizes(False)
            content_w = popup.sizeHintForColumn(0)
            popup.setUniformItemSizes(True)
            width = max(width, content_w + 2 * popup.frameWidth() + COMPLETION_FRAME_PADDING)
        row_h = popup.sizeHintForRow(0) if popup.count() else metrics.height() + COMPLETION_ROW_PADDING
        visible = min(popup.count(), AttributePopup.MAX_VISIBLE)
        popup.setFixedWidth(width)
        popup.setFixedHeight(visible * row_h + 2 * popup.frameWidth() + COMPLETION_ROW_PADDING)

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
        ctx = _detect_completion_context(self._scan_text(), cursor.position())
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
        self._on_scan_changed()
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
            self._on_scan_changed()
        finally:
            cursor.endEditBlock()
        self._refresh_completion()

    def mousePressEvent(self, event):
        self._hide_completion()
        super().mousePressEvent(event)
        self._refresh_completion()

    def focusOutEvent(self, event):
        self._hide_completion()
        super().focusOutEvent(event)

    def _handle_key(self, event):
        if event.key() in (Qt.Key_Backspace, Qt.Key_Delete):
            deleting_forward = event.key() == Qt.Key_Delete
            cursor = self.textCursor()

            if not cursor.hasSelection():
                plain = self._scan_text()
                pos = cursor.position()
                if deleting_forward and plain[pos:pos + 2] == LINK_PLACEHOLDER:
                    cursor.setPosition(pos + 2)
                    self.setTextCursor(cursor)
                    return
                if (not deleting_forward and pos >= 2
                        and plain[pos - 2:pos] == LINK_PLACEHOLDER):
                    cursor.setPosition(pos - 2)
                    self.setTextCursor(cursor)
                    return

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

            text = self._scan_text()
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
