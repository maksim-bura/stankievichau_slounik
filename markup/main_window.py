import os
import re
import xml.etree.ElementTree as ElementTree
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QListWidget, QListWidgetItem, QApplication, QPushButton, QMessageBox,
    QStyleOptionViewItem, QStyle
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QBrush, QPalette
from utils.text_utils import remove_accents, normalize_jo
from db.build_database import get_source_path
from app.widgets import SearchBox, ElidingDelegate, select_row, navigate_rows
from markup.editor import MarkupEditor
from markup.checked_state import CheckedState
from markup.styles import (
    MARKUP_GLOBAL_STYLE, ENTRY_LIST_STYLE,
    CHECKED_TOGGLE_STYLE, TAG_BUTTON_STYLE
)
from theme.layout_constants import (
    RESULTS_MIN_WIDTH, ENTRY_MIN_WIDTH,
    WINDOW_DEFAULT_WIDTH, WINDOW_DEFAULT_HEIGHT,
    LAYOUT_MARGINS, LAYOUT_SPACING, TOP_LAYOUT_SPACING,
    BUTTON_SIZE, LIST_ITEM_BORDER_WIDTH
)

_COLOR_NORMAL_BG = QColor(255, 255, 255)
_COLOR_HOVER_BG = QColor(250, 250, 250)
_COLOR_SELECTED_BG = QColor(237, 247, 253)
_COLOR_BORDER_DEFAULT = QColor(192, 192, 192)
_COLOR_BORDER_SELECTED = QColor(124, 158, 192)
_COLOR_CHECKED_BG = QColor(200, 247, 197)
_COLOR_CHECKED_HOVER_BG = QColor(184, 240, 181)
_COLOR_CHECKED_SELECTED_BG = QColor(124, 191, 122)
_COLOR_CHECKED_BORDER = QColor(160, 216, 160)

_HEADWORD_OPTIONS = {
    'search_in_headwords': True,
    'search_in_translations': False,
    'search_in_examples': False,
}


class _BorderDelegate(ElidingDelegate):
    def __init__(self, list_widget, checked_state):
        super().__init__(list_widget)
        self._checked_state = checked_state
        self._hovered_row = -1

    def paint(self, painter, option, index):
        item = self._list.itemFromIndex(index)
        if not item:
            super().paint(painter, option, index)
            return

        source_file = item.data(Qt.UserRole + 3)
        headword = item.data(Qt.UserRole + 1)
        entry_link = item.data(Qt.UserRole)
        is_checked = source_file and headword and self._checked_state.is_checked(source_file, entry_link, headword)
        is_selected = bool(option.state & QStyle.State_Selected)
        is_hovered = index.row() == self._hovered_row

        if is_checked:
            if is_selected:
                bg = _COLOR_CHECKED_SELECTED_BG
                border = _COLOR_CHECKED_SELECTED_BG
            elif is_hovered:
                bg = _COLOR_CHECKED_HOVER_BG
                border = _COLOR_CHECKED_BORDER
            else:
                bg = _COLOR_CHECKED_BG
                border = _COLOR_CHECKED_BORDER
        else:
            if is_selected:
                bg = _COLOR_SELECTED_BG
                border = _COLOR_BORDER_SELECTED
            elif is_hovered:
                bg = _COLOR_HOVER_BG
                border = _COLOR_BORDER_DEFAULT
            else:
                bg = _COLOR_NORMAL_BG
                border = QColor(0, 0, 0, 0)

        painter.save()
        painter.fillRect(option.rect, bg)
        if border.alpha() > 0:
            painter.fillRect(option.rect.x(), option.rect.y(), LIST_ITEM_BORDER_WIDTH, option.rect.height(), border)

        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        opt.backgroundBrush = QBrush(bg)

        palette = opt.palette
        palette.setColor(QPalette.Text, QColor(0, 0, 0))
        palette.setColor(QPalette.HighlightedText, QColor(0, 0, 0))
        opt.palette = palette

        style = option.widget.style() if option.widget else QApplication.style()
        style.drawControl(QStyle.CE_ItemViewItem, opt, painter, option.widget)

        painter.restore()


class MarkupMainWindow(QMainWindow):
    def __init__(self, search_engine):
        super().__init__()

        self.search_engine = search_engine
        self.checked_state = CheckedState()
        self.checked_state.migrate(self.search_engine._get_connection())
        self.current_result = None
        self._has_unsaved = False

        self.setWindowTitle('Dictionary Markup')
        self.resize(WINDOW_DEFAULT_WIDTH, WINDOW_DEFAULT_HEIGHT)

        self.setup_ui()
        self.load_styles()

        self.search_box.navigate_up.connect(
            lambda: navigate_rows(self.results_box, -1))
        self.search_box.navigate_down.connect(
            lambda: navigate_rows(self.results_box, 1))
        self.search_box.activate.connect(
            lambda: self._on_activate())

    def showEvent(self, event):
        super().showEvent(event)
        if not getattr(self, '_initial_shown', False):
            self._initial_shown = True
            self.show_all_entries()

    def setup_ui(self):
        central_widget = QWidget()
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(*LAYOUT_MARGINS)
        main_layout.setSpacing(LAYOUT_SPACING)

        top_layout = QHBoxLayout()
        top_layout.setSpacing(TOP_LAYOUT_SPACING)

        self.search_box = SearchBox('Search entries...')
        self.search_box.textChanged.connect(self.on_search)

        self._checked_toggle = QPushButton('\u2b1c')
        self._checked_toggle.setCheckable(True)
        self._checked_toggle.setFixedSize(BUTTON_SIZE)
        self._checked_toggle.setCursor(Qt.PointingHandCursor)
        self._checked_toggle.setStyleSheet(CHECKED_TOGGLE_STYLE)
        self._checked_toggle.clicked.connect(self._on_checked_toggle)

        self._save_button = QPushButton('\U0001f4be')
        self._save_button.setFixedSize(BUTTON_SIZE)
        self._save_button.setCursor(Qt.PointingHandCursor)
        self._save_button.setStyleSheet(TAG_BUTTON_STYLE)
        self._save_button.clicked.connect(self._on_save)
        self._save_button.hide()

        top_layout.addWidget(self.search_box, 1)
        top_layout.addWidget(self._checked_toggle)
        top_layout.addWidget(self._save_button)

        self.results_box = QListWidget()
        self.results_box.setFocusPolicy(Qt.NoFocus)
        self.results_box.setStyleSheet(ENTRY_LIST_STYLE)
        self.results_box.itemClicked.connect(self.on_result_clicked)
        self.results_box.setFixedWidth(RESULTS_MIN_WIDTH)
        self.results_box.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._delegate = _BorderDelegate(self.results_box, self.checked_state)
        self.results_box.setItemDelegate(self._delegate)
        self.results_box.setMouseTracking(True)
        self.results_box.viewport().installEventFilter(self)

        self.editor = MarkupEditor()
        self.editor.editor.setMinimumWidth(ENTRY_MIN_WIDTH)
        self.editor.editor.content_changed.connect(self._on_content_changed)

        bottom_layout = QHBoxLayout()
        bottom_layout.setSpacing(0)
        bottom_layout.setContentsMargins(*LAYOUT_MARGINS)
        bottom_layout.addWidget(self.results_box)
        bottom_layout.addWidget(self.editor)
        bottom_layout.setStretch(0, 0)
        bottom_layout.setStretch(1, 1)

        main_layout.addLayout(top_layout)
        main_layout.addLayout(bottom_layout)
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)

    def eventFilter(self, obj, event):
        if obj == self.results_box.viewport():
            if event.type() == event.Type.MouseMove:
                pos = event.position()
                item = self.results_box.itemAt(pos.toPoint())
                row = self.results_box.row(item) if item else -1
                if row != self._delegate._hovered_row:
                    self._delegate._hovered_row = row
                    self.results_box.viewport().update()
            elif event.type() == event.Type.Leave:
                if self._delegate._hovered_row != -1:
                    self._delegate._hovered_row = -1
                    self.results_box.viewport().update()
        return super().eventFilter(obj, event)

    def load_styles(self):
        QApplication.instance().setStyleSheet(MARKUP_GLOBAL_STYLE)

    def show_all_entries(self):
        results = self.search_engine.search('', **_HEADWORD_OPTIONS)
        self._display_results(results)

    def on_search(self, text):
        results = self.search_engine.search(text.strip(), **_HEADWORD_OPTIONS)
        self._display_results(results)

    def _display_results(self, results):
        self.current_results = results
        self.results_box.clear()

        if not results:
            return

        for r in results:
            item = QListWidgetItem(remove_accents(r[1]))
            item.setData(Qt.UserRole, r[3])
            item.setData(Qt.UserRole + 1, r[1])
            item.setData(Qt.UserRole + 2, r[0])
            item.setData(Qt.UserRole + 3, r[4])
            self.results_box.addItem(item)

        if results:
            select_row(self.results_box, 0)

    def _on_activate(self):
        item = self.results_box.currentItem()
        if item:
            self.on_result_clicked(item)

    def on_result_clicked(self, item):
        if self._has_unsaved:
            self._save_current()

        entry_id = item.data(Qt.UserRole + 2)
        headword = item.data(Qt.UserRole + 1)
        if not headword:
            return

        result = None
        for r in self.current_results:
            if r[0] == entry_id and r[1] == headword:
                result = r
                break

        if not result:
            return

        source_file = result[4]
        xml_text = result[2]

        if self._has_unsaved or not xml_text:
            fresh = self._read_entry_from_source(entry_id, source_file, headword, result[3])
            if fresh is not None:
                xml_text = fresh
                for i, r in enumerate(self.current_results):
                    if r[0] == entry_id:
                        self.current_results[i] = (r[0], r[1], fresh, r[3], r[4])
                        break

        self.current_result = (result[0], result[1], xml_text, result[3], source_file)
        self.editor.editor.set_entry(result[0], xml_text)
        self._has_unsaved = False

        is_checked = self.checked_state.is_checked(source_file, result[3], result[1])
        self._checked_toggle.setText('\u2705' if is_checked else '\u2b1c')
        self._checked_toggle.setChecked(is_checked)
        self._save_button.hide()

    def _read_entry_from_source(self, entry_id, source_file, headword=None, entry_link=None):
        if not source_file:
            return None
        file_path = get_source_path(source_file)
        if not os.path.exists(file_path):
            return None
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            if headword is None and self.current_result and self.current_result[0] == entry_id:
                headword = self.current_result[1]
            if entry_link is None and self.current_result and self.current_result[0] == entry_id:
                entry_link = self.current_result[3]

            blocks = re.findall(r'<entry\b.*?</entry>', content, re.DOTALL)
            t_norm = normalize_jo(remove_accents(headword.lower())) if headword else None
            link_norm = normalize_jo(remove_accents(entry_link.lower())) if entry_link else None

            if link_norm:
                for block in blocks:
                    if self._block_link_matches(block, link_norm) and (t_norm is None or self._block_matches(block, t_norm)):
                        return block

            if t_norm:
                for block in blocks:
                    if self._block_matches(block, t_norm):
                        return block

            root = ElementTree.fromstring(content)
            entries = list(root.iter('entry'))
            if entries:
                return ElementTree.tostring(entries[0], encoding='unicode')
        except (ElementTree.ParseError, OSError):
            pass
        return None

    @staticmethod
    def _block_link_matches(block, link_norm):
        m = re.search(r'<entry\b[^>]*\blink="([^"]*)"', block)
        if not m:
            return False
        return normalize_jo(remove_accents(m.group(1))) == link_norm

    @staticmethod
    def _block_matches(block, target_norm):
        for m in re.finditer(r'<hw>([^<]*)</hw>', block):
            hw_norm = normalize_jo(remove_accents(m.group(1).lower()))
            if hw_norm == target_norm:
                return True
        return False

    def _on_checked_toggle(self):
        if not self.current_result:
            return
        entry_id = self.current_result[0]
        headword = self.current_result[1]
        source_file = self.current_result[4]
        entry_link = self.current_result[3]
        new_state = self.checked_state.toggle(source_file, entry_link, headword)
        self._checked_toggle.setText('\u2705' if new_state else '\u2b1c')
        self._checked_toggle.setChecked(new_state)
        self.results_box.viewport().update()

    def _on_save(self):
        self._save_current()

    def _save_current(self):
        if not self.current_result or not self.editor.editor.is_modified():
            return

        entry_id = self.current_result[0]
        source_file = self.current_result[4]
        new_xml = self.editor.editor.get_xml()

        try:
            root = ElementTree.fromstring(new_xml)
            new_entry_string = ElementTree.tostring(root, encoding='unicode')
        except ElementTree.ParseError:
            QMessageBox.warning(self, 'Invalid XML', 'The entry contains invalid XML.')
            return

        if not source_file:
            QMessageBox.warning(self, 'Save Error', 'No source file found for this entry.')
            return

        file_path = get_source_path(source_file)

        if not os.path.exists(file_path):
            QMessageBox.warning(self, 'Save Error', f'Source file not found: {source_file}')
            return

        old_entry_string = self._read_entry_from_source(
            entry_id, source_file,
            self.current_result[1] if self.current_result else None,
            self.current_result[3] if self.current_result else None
        )
        if not old_entry_string:
            QMessageBox.warning(self, 'Save Error', 'Could not locate the original entry in the source file.')
            return

        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        old_entry_string = old_entry_string.rstrip('\n')
        new_entry_string = new_entry_string.rstrip('\n')

        if old_entry_string not in content:
            QMessageBox.warning(self, 'Save Error', 'Could not locate the original entry in the source file.')
            return

        new_content = content.replace(old_entry_string, new_entry_string, 1)

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)

        self._has_unsaved = False
        self.editor.editor._is_modified = False
        self._save_button.hide()

        updated = (entry_id, self.current_result[1], new_entry_string, self.current_result[3], source_file)
        self.current_result = updated
        for i, r in enumerate(self.current_results):
            if r[0] == entry_id:
                self.current_results[i] = (r[0], r[1], new_entry_string, r[3], r[4])

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_S and event.modifiers() == Qt.ControlModifier:
            self._on_save()
            event.accept()
        else:
            super().keyPressEvent(event)

    def _on_content_changed(self):
        self._has_unsaved = True
        self._save_button.show()

    def closeEvent(self, event):
        if self._has_unsaved:
            self._save_current()
        event.accept()
