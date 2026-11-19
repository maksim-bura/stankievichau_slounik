from PySide6.QtWidgets import QApplication, QListWidgetItem
from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor

from dictionary_app.utils.xml_schema import BOOL as _ATTR_BOOL
from markup_app.panels.attribute_popup import AttributePopup
from markup_app.services.completion_context import detect_context
from markup_app.theme.layout_constants import (
    COMPLETION_FRAME_PADDING, COMPLETION_MIN_WIDTH, COMPLETION_ROW_PADDING
)


class CompletionController:
    def __init__(self, edit):
        self._edit = edit
        self._popup = AttributePopup(edit)
        self._popup.hide()
        self._popup.itemClicked.connect(self._accept_item)

    def handle_key(self, event):
        popup = self._popup
        if not popup.isVisible():
            return False
        key = event.key()
        if key == Qt.Key_Escape:
            self.hide()
            return True
        if key == Qt.Key_Down:
            self._move_selection(1)
            return True
        if key == Qt.Key_Up:
            self._move_selection(-1)
            return True
        if key in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Tab):
            self._accept_current()
            return True
        if key in (Qt.Key_Left, Qt.Key_Right, Qt.Key_Home, Qt.Key_End):
            self.hide()
        return False

    def refresh(self):
        edit = self._edit
        pos = edit.textCursor().position()
        ctx = detect_context(edit._scan_text(), pos)
        if ctx is None:
            self.hide()
            return
        items = ctx.candidates()
        if not items:
            self.hide()
            return
        self._show(items)

    def hide(self):
        self._popup.hide()

    def _show(self, items):
        popup = self._popup
        popup.clear()
        for name, kind in items:
            item = QListWidgetItem(name)
            item.setData(Qt.UserRole, (name, kind))
            popup.addItem(item)
        popup.setCurrentRow(0)
        self._size_popup()
        self._position_popup()
        if not popup.isVisible():
            popup.show()
        popup.raise_()

    def _size_popup(self):
        popup = self._popup
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

    def _position_popup(self):
        edit = self._edit
        popup = self._popup
        rect = edit.cursorRect()
        global_pos = edit.viewport().mapToGlobal(rect.bottomLeft())
        screen = QApplication.screenAt(global_pos) or edit.screen()
        avail = screen.availableGeometry()
        x = min(max(global_pos.x(), avail.left()), avail.right() - popup.width())
        y = global_pos.y()
        if y + popup.height() > avail.bottom():
            y = edit.viewport().mapToGlobal(rect.topLeft()).y() - popup.height()
        popup.move(x, y)

    def _move_selection(self, delta):
        popup = self._popup
        if popup.count() == 0:
            return
        popup.setCurrentRow((popup.currentRow() + delta) % popup.count())

    def _accept_current(self):
        item = self._popup.currentItem()
        if item is not None:
            self._apply(item.data(Qt.UserRole))

    def _accept_item(self, item):
        if item is not None:
            self._apply(item.data(Qt.UserRole))

    def _apply(self, data):
        if not data:
            return
        edit = self._edit
        name, kind = data
        cursor = edit.textCursor()
        ctx = detect_context(edit._scan_text(), cursor.position())
        if ctx is None:
            self.hide()
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
        edit._on_scan_changed()
        cursor.endEditBlock()
        edit.setTextCursor(cursor)
        self.hide()
