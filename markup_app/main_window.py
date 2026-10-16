import os
import re
import xml.etree.ElementTree as ElementTree
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QListView, QApplication, QPushButton, QMessageBox,
    QMenu, QWidgetAction
)
from PySide6.QtCore import Qt, QPoint, QEvent, QRect, QItemSelectionModel
from PySide6.QtGui import QCursor
from dictionary_app.utils.text_utils import remove_accents, resolve_headword, hw_identity, has_keep_acc, collapse_same_entry_duplicates
from dictionary_app.utils.xml_schema import ATTR_ID
from dictionary_app.db.build_database import build_database, get_source_path
from markup_app.services.broken_links import (
    BrokenLinkAnalyzer,
    MODE_AMBIGUOUS_G,
    MODE_MISSING,
    MODE_UNRESOLVED,
    MODE_UNION,
    normalize_headword,
    row_norm,
)
from dictionary_app.widgets import (
    SearchBox, select_row, navigate_rows, INSERT_LETTER_G,
    InsertLetterGButton
)
from markup_app.panels.editor import MarkupEditor
from markup_app.services.checked_state import CheckedState
from markup_app.services.duplicates import DuplicateResolver
from markup_app.services.link_marks import build_link_marks
from markup_app.panels.results_widgets import (
    BorderDelegate, BrokenCheckOption, MenuCommandOption, ResultsListModel,
    apply_pressed,
)
from markup_app.theme.styles import (
    MARKUP_GLOBAL_STYLE, ENTRY_LIST_STYLE,
    REBUILD_BUTTON_STYLE
)
from markup_app.localization import strings
from dictionary_app.theme.layout_constants import (
    RESULTS_MIN_WIDTH, ENTRY_MIN_WIDTH,
    WINDOW_DEFAULT_WIDTH, WINDOW_DEFAULT_HEIGHT,
    LAYOUT_MARGINS, LAYOUT_SPACING, TOP_LAYOUT_SPACING,
    BUTTON_SIZE,
)
from dictionary_app.theme.widget_styles import MENU_BUTTON_STYLE
from dictionary_app.utils.constants import CHECK_MARK, CHECK_BLANK
from dictionary_app.utils.item_roles import (
    ROLE_ENTRY_LINK, ROLE_HEADWORD, ROLE_ENTRY_ID,
)
from markup_app.utils.constants import (
    RELOAD_MARKER, DUPLICATES_MARKER, BROKEN_LINKS_MARKER,
)

_ENTRY_BLOCK_RE = re.compile(r'<entry\b.*?</entry>', re.DOTALL)


def find_entry_blocks(content):
    return _ENTRY_BLOCK_RE.findall(content)


class MarkupMainWindow(QMainWindow):
    def __init__(self, search_engine):
        super().__init__()

        self.search_engine = search_engine
        self.checked_state = CheckedState()
        self.checked_state.migrate(self.search_engine._get_connection())
        self.current_result = None
        self.current_occurrence = None
        self.current_results = []
        self._has_unsaved = False
        self._loaded_raw = {}
        self._by_id_headword = {}
        self._source_cache = {}
        self._sub_headword_cache = {}
        self._duplicate_resolver = DuplicateResolver(self.search_engine)
        self._broken_mode = None
        self._broken_links = BrokenLinkAnalyzer(
            self.search_engine._get_connection,
            self._iter_source_blocks,
        )


        self.setWindowTitle(strings.window.title)
        self.resize(WINDOW_DEFAULT_WIDTH, WINDOW_DEFAULT_HEIGHT)

        self.setup_ui()
        self.load_styles()

        self.search_box.navigate_up.connect(
            lambda: navigate_rows(self.results_box, self.results_model, -1))
        self.search_box.navigate_down.connect(
            lambda: navigate_rows(self.results_box, self.results_model, 1))
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

        self.search_box = SearchBox(strings.search_boxes.entries.placeholder)
        self.search_box.textChanged.connect(self.on_search)

        self._insert_letter_g_button = InsertLetterGButton()
        self._insert_letter_g_button.clicked.connect(self._insert_letter_g)

        self._duplicates_toggle = QPushButton(DUPLICATES_MARKER)
        self._duplicates_toggle.setCheckable(True)
        self._duplicates_toggle.setFixedSize(BUTTON_SIZE)
        self._duplicates_toggle.setCursor(Qt.PointingHandCursor)
        self._duplicates_toggle.setProperty("class", "menu-button")
        self._duplicates_toggle.setStyleSheet(MENU_BUTTON_STYLE)
        self._duplicates_toggle.setToolTip(strings.app_buttons.duplicates.tooltip)
        self._duplicates_toggle.clicked.connect(self._on_duplicates_toggle)
        self._update_duplicates_pressed()

        self._broken_links_toggle = QPushButton(BROKEN_LINKS_MARKER)
        self._broken_links_toggle.setCheckable(True)
        self._broken_links_toggle.setFixedSize(BUTTON_SIZE)
        self._broken_links_toggle.setCursor(Qt.PointingHandCursor)
        self._broken_links_toggle.setProperty("class", "menu-button")
        self._broken_links_toggle.setStyleSheet(MENU_BUTTON_STYLE)
        self._broken_links_toggle.setToolTip(strings.app_buttons.broken_links.tooltip)
        self._broken_links_toggle.clicked.connect(self._on_broken_links_toggle)
        self._update_broken_links_pressed()

        self._broken_menu = QMenu(self)
        self._broken_menu_options = {}
        for key, text in (
                (MODE_MISSING, strings.app_buttons.broken_links.dropdown.missing_links),
                (MODE_UNRESOLVED, strings.app_buttons.broken_links.dropdown.unresolved_links),
                (MODE_AMBIGUOUS_G, strings.app_buttons.broken_links.dropdown.ambiguous_grammar)):
            option = BrokenCheckOption(text)
            option.clicked.connect(self._on_broken_category_toggled)
            self._broken_menu_options[key] = option
            _option_action = QWidgetAction(self._broken_menu)
            _option_action.setDefaultWidget(option)
            self._broken_menu.addAction(_option_action)
        self._broken_menu.aboutToHide.connect(self._on_broken_menu_closed)
        self._broken_menu_consume = False
        self._broken_links_toggle.setContextMenuPolicy(Qt.CustomContextMenu)
        self._broken_links_toggle.customContextMenuRequested.connect(
            self._on_broken_menu_requested
        )
        self._broken_links_toggle.installEventFilter(self)

        self._rebuild_button = QPushButton(RELOAD_MARKER)
        self._rebuild_button.setFixedSize(BUTTON_SIZE)
        self._rebuild_button.setCursor(Qt.PointingHandCursor)
        self._rebuild_button.setStyleSheet(REBUILD_BUTTON_STYLE)
        self._rebuild_button.setToolTip(strings.app_buttons.rebuild_database.tooltip)
        self._rebuild_button.clicked.connect(self._on_rebuild)

        self._checked_menu = QMenu(self)
        _menu_option = MenuCommandOption(
            strings.editor.entry_status.dropdown.uncheck_all, self._on_uncheck_all
        )
        _menu_option_action = QWidgetAction(self._checked_menu)
        _menu_option_action.setDefaultWidget(_menu_option)
        self._checked_menu.addAction(_menu_option_action)
        self._checked_menu.aboutToHide.connect(self._on_checked_menu_closed)
        self._checked_menu_consume = False

        top_layout.addWidget(self.search_box, 1)
        top_layout.addWidget(self._insert_letter_g_button)
        top_layout.addWidget(self._duplicates_toggle)
        top_layout.addWidget(self._broken_links_toggle)
        top_layout.addWidget(self._rebuild_button)

        self.results_box = QListView()
        self.results_box.setFocusPolicy(Qt.NoFocus)
        self.results_box.setStyleSheet(ENTRY_LIST_STYLE)
        self.results_model = ResultsListModel()
        self.results_box.setModel(self.results_model)
        self.results_box.clicked.connect(self.on_result_clicked)
        self.results_box.setFixedWidth(RESULTS_MIN_WIDTH)
        self.results_box.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.results_box.setUniformItemSizes(True)
        self._delegate = BorderDelegate(self.results_box, self.checked_state)
        self.results_box.setItemDelegate(self._delegate)
        self.results_box.setMouseTracking(True)
        self.results_box.viewport().installEventFilter(self)

        self.editor = MarkupEditor()
        self.editor.pane.setMinimumWidth(ENTRY_MIN_WIDTH)
        self.editor.pane.content_changed.connect(self._on_content_changed)
        self._checked_toggle = self.editor.checked_toggle
        self._checked_toggle.clicked.connect(self._on_checked_toggle)
        self._checked_toggle.setContextMenuPolicy(Qt.CustomContextMenu)
        self._checked_toggle.customContextMenuRequested.connect(
            self._on_checked_menu_requested
        )
        self._checked_toggle.installEventFilter(self)
        self._update_checked_pressed()

        self._save_button = self.editor.save_button
        self._save_button.setToolTip(strings.editor.save.tooltip)
        self._save_button.clicked.connect(self._on_save)

        bottom_layout = QHBoxLayout()
        bottom_layout.setSpacing(LAYOUT_SPACING)
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
        if obj == self._checked_toggle:
            if (event.type() == QEvent.MouseButtonPress
                    and self._checked_menu_consume):
                self._checked_menu_consume = False
                return True
        if obj == self._broken_links_toggle:
            if (event.type() == QEvent.MouseButtonPress
                    and self._broken_menu_consume):
                self._broken_menu_consume = False
                return True
        if (getattr(self, 'results_box', None) is not None
                and obj == self.results_box.viewport()):
            if event.type() == event.Type.MouseMove:
                pos = event.position()
                index = self.results_box.indexAt(pos.toPoint())
                row = index.row() if index.isValid() else -1
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
        results = self.search_engine.search_headwords('')
        self._display_results(results)

    def on_search(self, text):
        results = self.search_engine.search_headwords(text.strip())
        self._display_results(results)

    def _display_results(self, results):
        self.current_results = results
        if self._duplicates_toggle.isChecked() or self._broken_mode is not None:
            displayed = self._duplicate_resolver.filter(results) if self._duplicates_toggle.isChecked() else results
            if self._broken_mode is not None:
                displayed = self._broken_filter(displayed, self._broken_mode)
        else:
            displayed = collapse_same_entry_duplicates(results)
        self._by_id_headword = {(r[0], r[1], r[3]): r for r in displayed}
        self.results_model.set_rows(
            [(resolve_headword(r[1], r[6] if len(r) > 6 else 0), r) for r in displayed])

        if displayed:
            select_row(self.results_box, self.results_model, 0)

    def _broken_filter(self, results, mode):
        flags = self._broken_links.flags()
        if isinstance(mode, str):
            wanted = (
                {MODE_MISSING, MODE_UNRESOLVED, MODE_AMBIGUOUS_G}
                if mode == MODE_UNION else {mode}
            )
        else:
            wanted = set(mode)
        if not wanted:
            return list(results)
        filtered = []
        for r in results:
            norm = row_norm(r[1])
            row_flags = flags.get((r[4], r[0], norm)) or flags.get((r[4], None, norm))
            if not row_flags:
                continue
            if wanted & row_flags:
                filtered.append(r)
        return filtered

    def _see_span_mode(self):
        active = self._broken_mode or set()
        see = active & {MODE_MISSING, MODE_UNRESOLVED}
        if len(see) == 2:
            return MODE_UNION
        if see:
            return next(iter(see))
        return None

    def _refresh_broken_highlight(self):
        text = self.editor.pane.get_xml()
        mode = self._see_span_mode()
        spans = self._broken_links.spans(text, mode) if mode else []
        self.editor.pane.highlight_broken_links(spans)
        if self._broken_mode and MODE_AMBIGUOUS_G in self._broken_mode:
            g_spans, hw_spans = self._broken_links.ambiguous_spans(text)
            self.editor.pane.highlight_grammar_marks(g_spans, hw_spans)
        else:
            self.editor.pane.clear_grammar_marks()

    def _refresh_link_marks(self):
        if not self.current_result:
            return
        offsets, tooltips = build_link_marks(
            self._broken_links, self.editor.pane.get_xml(), self.current_result[0]
        )
        self.editor.pane.set_link_marks(offsets, tooltips)

    def _iter_source_blocks(self):
        cursor = self.search_engine._get_connection().cursor()
        cursor.execute("SELECT DISTINCT source_file FROM dictionary")
        source_files = [r[0] for r in cursor.fetchall() if r[0]]
        for source_file in source_files:
            loaded = self._load_source_content(source_file)
            if loaded is None:
                continue
            for block in loaded['blocks']:
                yield source_file, block

    def _on_broken_category_toggled(self, option):
        key = next(
            (k for k, opt in self._broken_menu_options.items() if opt is option),
            None,
        )
        if key is None:
            return
        selected = [k for k, opt in self._broken_menu_options.items() if opt.is_checked()]
        if not selected:
            option.set_checked(True)
            selected = [key]
        self._sync_broken_option_active()
        mode = (
            MODE_UNION
            if len(selected) == len(self._broken_menu_options)
            else frozenset(selected)
        )
        self._apply_broken_mode(mode)

    def _on_broken_links_toggle(self):
        self._apply_broken_mode(
            MODE_UNION if self._broken_links_toggle.isChecked() else None
        )

    def _apply_broken_mode(self, mode):
        if mode is None:
            self._broken_mode = None
        elif isinstance(mode, str):
            self._broken_mode = (
                {MODE_MISSING, MODE_UNRESOLVED, MODE_AMBIGUOUS_G}
                if mode == MODE_UNION else {mode}
            )
        else:
            self._broken_mode = set(mode)
        if not self._broken_mode:
            self._broken_mode = None
        self._broken_links_toggle.setChecked(self._broken_mode is not None)
        self._sync_broken_options()
        self._update_broken_links_pressed()
        self._display_results(self.current_results)
        self._refresh_broken_highlight()

    def _sync_broken_options(self):
        for key, opt in self._broken_menu_options.items():
            opt.set_checked(
                True if self._broken_mode is None else key in self._broken_mode
            )
        self._sync_broken_option_active()

    def _sync_broken_option_active(self):
        options = list(self._broken_menu_options.values())
        checked = [opt for opt in options if opt.is_checked()]
        for opt in options:
            opt.set_active(
                not (len(checked) == 1 and opt is checked[0])
            )

    def _on_broken_menu_requested(self, _pos):
        self._broken_menu_consume = False
        self._sync_broken_options()
        self._open_button_menu(self._broken_links_toggle, self._broken_menu)

    def _on_broken_menu_closed(self):
        self._broken_menu_consume = self._button_menu_consumed(self._broken_links_toggle)
        self._update_broken_links_pressed()

    def _update_duplicates_pressed(self):
        apply_pressed(self._duplicates_toggle)

    def _update_broken_links_pressed(self):
        apply_pressed(self._broken_links_toggle)

    def _update_checked_pressed(self):
        apply_pressed(self._checked_toggle)
        tooltip = (
            strings.editor.entry_status.checked.tooltip
            if self._checked_toggle.isChecked()
            else strings.editor.entry_status.unchecked.tooltip
        )
        self._checked_toggle.setToolTip(tooltip)

    def _apply_checked_visual(self, is_checked):
        glyph = CHECK_MARK if is_checked else CHECK_BLANK
        self._checked_toggle.setText(glyph)
        self._checked_toggle.setChecked(is_checked)
        self._update_checked_pressed()

    @staticmethod
    def _open_button_menu(button, menu, anchor=None):
        button.setProperty('pressed', 'menu')
        button.style().unpolish(button)
        button.style().polish(button)
        if anchor is None:
            anchor = button.height()
        menu.popup(button.mapToGlobal(QPoint(0, anchor)))

    @staticmethod
    def _button_menu_consumed(button):
        rect = QRect(button.mapToGlobal(QPoint(0, 0)), button.size())
        return rect.contains(QCursor.pos())


    def _insert_letter_g(self):
        focus_widget = QApplication.focusWidget()
        if isinstance(focus_widget, SearchBox):
            focus_widget.insert(INSERT_LETTER_G)
            return
        self.search_box.setFocus()
        self.search_box.insert(INSERT_LETTER_G)

    def _on_duplicates_toggle(self):
        self._update_duplicates_pressed()
        self._display_results(self.current_results)

    def _on_activate(self):
        index = self.results_box.currentIndex()
        if index.isValid():
            self.on_result_clicked(index)

    def _confirm_leave(self):
        if not self._has_unsaved:
            return True

        box = QMessageBox(self)
        box.setIcon(QMessageBox.Question)
        box.setWindowTitle(strings.dialog.unsaved_changes.title)
        box.setText(strings.dialog.unsaved_changes.body)
        save_btn = box.addButton(strings.dialog.unsaved_changes.buttons.save, QMessageBox.AcceptRole)
        leave_btn = box.addButton(strings.dialog.unsaved_changes.buttons.discard, QMessageBox.DestructiveRole)
        cancel_btn = box.addButton(strings.dialog.unsaved_changes.buttons.cancel, QMessageBox.RejectRole)
        box.setDefaultButton(cancel_btn)
        box.exec()

        clicked = box.clickedButton()
        if clicked is save_btn:
            if self.editor.pane.is_modified() and self.current_result:
                self._save_current()
                if self.editor.pane.is_modified():
                    return False
            return True
        if clicked is leave_btn:
            return True
        return False

    def _restore_selection_to_current(self):
        current = self.current_result
        if not current:
            return
        for i, (_display, r) in enumerate(self.results_model.rows):
            if (r[0], r[1], r[3]) == (current[0], current[1], current[3]):
                self.results_box.selectionModel().setCurrentIndex(
                    self.results_model.index(i, 0),
                    QItemSelectionModel.SelectionFlag.NoUpdate)
                return

    def on_result_clicked(self, index):
        entry_id = index.data(ROLE_ENTRY_ID)
        headword = index.data(ROLE_HEADWORD)
        entry_link = index.data(ROLE_ENTRY_LINK)
        if not headword:
            return

        occurrence = 0
        occurrence_idx = 0
        for i, (_display, r) in enumerate(self.results_model.rows):
            if (r[0], r[1], r[3]) == (entry_id, headword, entry_link):
                if i == index.row():
                    occurrence = occurrence_idx
                    break
                occurrence_idx += 1

        result = self._by_id_headword.get((entry_id, headword, entry_link))
        if not result:
            return

        current = self.current_result
        if (current and self.current_occurrence == occurrence
                and (current[0], current[1], current[3]) == (entry_id, headword, entry_link)):
            return

        if not self._confirm_leave():
            self._restore_selection_to_current()
            return

        self._load_result(result, occurrence, self._separate_occurrences_mode())

    def _is_sub_headword(self, result):
        key = (result[0], result[1])
        cached = self._sub_headword_cache.get(key)
        if cached is None:
            cursor = self.search_engine._get_connection().cursor()
            cursor.execute("SELECT headword FROM dictionary WHERE id=?", (result[0],))
            row = cursor.fetchone()
            cached = bool(row) and row[0] != result[1]
            self._sub_headword_cache[key] = cached
        return cached

    def _load_result(self, result, occurrence=0, separate_occurrences=False):
        entry_id = result[0]
        headword = result[1]
        source_file = result[4]
        entry_link = result[3]
        keep_acc = result[6] if len(result) > 6 else 0

        raw = self._read_entry_from_source(entry_id, source_file, headword, entry_link, keep_acc)
        if raw is not None:
            self._loaded_raw[entry_id] = raw.rstrip('\n')
            xml_text = raw
        else:
            self._loaded_raw.pop(entry_id, None)
            xml_text = self.search_engine.get_full_entry(entry_id) or ''

        self.current_result = (result[0], result[1], xml_text, result[3], source_file, keep_acc)
        self.current_occurrence = occurrence
        self.editor.pane.set_entry(result[0], xml_text)
        if self._is_sub_headword(result):
            self.editor.pane.mark_sub_hw(
                result[1], occurrence, keep_acc, separate_occurrences)
        else:
            self.editor.pane.mark_main_non_d(result[1], occurrence, keep_acc)
        self._has_unsaved = False

        is_checked = self.checked_state.is_checked(source_file, result[3], result[1])
        self._apply_checked_visual(is_checked)
        self._save_button.hide()
        self._checked_toggle.show()
        self._refresh_broken_highlight()
        self._refresh_link_marks()

    def _read_entry_from_source(self, entry_id, source_file, headword=None, entry_link=None, keep_acc=0):
        if not source_file:
            return None
        if headword is None and self.current_result and self.current_result[0] == entry_id:
            headword = self.current_result[1]
        if entry_link is None and self.current_result and self.current_result[0] == entry_id:
            entry_link = self.current_result[3]

        loaded = self._load_source_content(source_file)
        if loaded is None:
            return None
        blocks = loaded['blocks']
        t_norm = hw_identity(headword, keep_acc) if headword else None
        link_norm = normalize_headword(entry_link) if entry_link else None

        def _matches_own_entry(candidates):
            if len(candidates) == 1:
                return blocks[candidates[0]]
            full = self.search_engine.get_full_entry(entry_id)
            if full is not None:
                target = re.sub(r'\s+', '', full)
                for i in candidates:
                    if re.sub(r'\s+', '', blocks[i]) == target:
                        return blocks[i]
            return blocks[candidates[0]]

        if link_norm:
            candidates = []
            for i in loaded['by_link'].get(link_norm, ()):
                block = blocks[i]
                if t_norm is None or self._block_matches(block, t_norm):
                    candidates.append(i)
            if candidates:
                return _matches_own_entry(candidates)

        if t_norm:
            candidates = []
            for i in loaded['by_headword'].get(t_norm, ()):
                block = blocks[i]
                if self._block_matches(block, t_norm):
                    candidates.append(i)
            if candidates:
                return _matches_own_entry(candidates)
        return None

    def _load_source_content(self, source_file):
        cached = self._source_cache.get(source_file)
        if cached is not None:
            return cached
        file_path = get_source_path(source_file)
        if not os.path.exists(file_path):
            return None
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except OSError:
            return None
        blocks = find_entry_blocks(content)
        by_link = {}
        by_headword = {}
        for i, block in enumerate(blocks):
            link_norm = self._block_link(block)
            if link_norm is not None:
                by_link.setdefault(link_norm, []).append(i)
            for hw_norm in self._block_headwords(block):
                by_headword.setdefault(hw_norm, []).append(i)
        loaded = {'content': content, 'blocks': blocks, 'by_link': by_link, 'by_headword': by_headword}
        self._source_cache[source_file] = loaded
        return loaded

    @staticmethod
    def _block_raw_id(block):
        m = re.search(r'<entry\b[^>]*\b' + ATTR_ID + r'="([^"]*)"', block)
        return m.group(1) if m else None

    @classmethod
    def _block_link(cls, block):
        raw = cls._block_raw_id(block)
        if not raw:
            return None
        return normalize_headword(raw)

    @staticmethod
    def _block_headwords(block):
        norms = []
        for m in re.finditer(r'<hw\b([^>]*)>(.*?)</hw>', block, re.DOTALL):
            inner = re.sub(r'<[^>]+>', '', m.group(2))
            norms.append(hw_identity(inner.strip(), has_keep_acc(m.group(1))))
        return norms

    @staticmethod
    def _block_matches(block, target_norm):
        return target_norm in MarkupMainWindow._block_headwords(block)

    def _on_checked_toggle(self):
        if not self.current_result:
            return
        entry_id = self.current_result[0]
        headword = self.current_result[1]
        source_file = self.current_result[4]
        entry_link = self.current_result[3]
        new_state = self.checked_state.toggle(source_file, entry_link, headword)
        self._apply_checked_visual(new_state)
        self.results_box.viewport().update()

    def _on_checked_menu_requested(self, _pos):
        self._checked_menu_consume = False
        metrics = self._checked_toggle.fontMetrics()
        baseline = (
            self._checked_toggle.height() // 2
            + (metrics.ascent() - metrics.descent()) // 2
        )
        self._open_button_menu(
            self._checked_toggle, self._checked_menu, baseline
        )

    def _on_checked_menu_closed(self):
        self._checked_menu_consume = self._button_menu_consumed(self._checked_toggle)
        self._update_checked_pressed()

    def _on_uncheck_all(self):
        self._checked_menu.close()
        self.checked_state.uncheck_all()
        self._apply_checked_visual(False)
        self.results_box.viewport().update()

    def _on_save(self):
        self._save_current()

    def _on_rebuild(self):
        if not self._confirm_leave():
            return

        search_text = self.search_box.text().strip()
        current = self.current_result

        self.search_engine.close()

        try:
            build_database()
        except Exception as exc:
            self.search_engine.close()
            QMessageBox.warning(self, 'Rebuild Error', f'Database rebuild failed:\n{exc}')
            return

        self._source_cache.clear()
        self._sub_headword_cache.clear()
        self._duplicate_resolver.invalidate()
        self._refresh_after_rebuild(search_text, current)

    def _refresh_after_rebuild(self, search_text, current):
        self._broken_links.invalidate()
        self.show_all_entries() if not search_text else self.on_search(search_text)

        if current and current[4]:
            result = self._find_current_result()
            if result is not None:
                self._load_result(result, self.current_occurrence, self._separate_occurrences_mode())

    def _separate_occurrences_mode(self):
        return self._duplicates_toggle.isChecked() or self._broken_mode is not None

    def _find_current_result(self):
        current = self.current_result
        for r in self.current_results:
            if r[4] == current[4] and r[1] == current[1] and r[3] == current[3]:
                return r
        return None

    def _save_current(self):
        if not self.current_result or not self.editor.pane.is_modified():
            return

        entry_id = self.current_result[0]
        source_file = self.current_result[4]
        new_xml = self.editor.pane.get_xml()

        try:
            root = ElementTree.fromstring(new_xml)
            new_entry_string = ElementTree.tostring(root, encoding='unicode').rstrip('\n')
        except ElementTree.ParseError:
            QMessageBox.warning(self, strings.dialog.invalid_xml.title,
                strings.dialog.invalid_xml.body)
            return

        if not source_file:
            QMessageBox.warning(self, 'Save Error', 'No source file found for this entry.')
            return

        file_path = get_source_path(source_file)

        if not os.path.exists(file_path):
            QMessageBox.warning(self, 'Save Error', f'Source file not found: {source_file}')
            return

        headword = self.current_result[1]
        entry_link = self.current_result[3]

        loaded = self._load_source_content(source_file)
        content = loaded['content'] if loaded else None
        blocks = loaded['blocks'] if loaded else []
        if not blocks:
            QMessageBox.warning(self, 'Save Error', 'Could not locate the original entry in the source file.')
            return

        old_raw = self._loaded_raw.get(entry_id)
        if old_raw is None:
            old_raw = self._read_entry_from_source(entry_id, source_file, headword, entry_link)

        indices = [i for i, b in enumerate(blocks) if b == old_raw] if old_raw else []

        if not indices:
            QMessageBox.warning(self, 'Save Error', 'Could not locate the original entry in the source file.')
            return
        if len(indices) != 1:
            QMessageBox.warning(self, 'Save Error',
                'The original entry could not be matched uniquely; no changes were saved.')
            return

        new_content = content.replace(blocks[indices[0]], new_entry_string, 1)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)

        self._source_cache.pop(source_file, None)
        self._loaded_raw[entry_id] = new_entry_string
        self._broken_links.invalidate()
        self._has_unsaved = False
        self.editor.pane.mark_saved()
        self._save_button.hide()

        updated = (entry_id, self.current_result[1], new_entry_string, entry_link, source_file, None)
        self.current_result = updated
        self._by_id_headword[(entry_id, updated[1], entry_link)] = updated
        for i, r in enumerate(self.current_results):
            if r[0] == entry_id:
                self.current_results[i] = (r[0], r[1], new_entry_string, r[3], r[4], None)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_S and event.modifiers() == Qt.ControlModifier:
            self._on_save()
            event.accept()
        else:
            super().keyPressEvent(event)

    def _on_content_changed(self):
        self._has_unsaved = self.editor.pane.is_modified()
        if self._has_unsaved:
            self._save_button.show()
        else:
            self._save_button.hide()

    def closeEvent(self, event):
        if not self._confirm_leave():
            event.ignore()
            return
        event.accept()

