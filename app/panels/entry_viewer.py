from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QSizePolicy, QTextBrowser, QVBoxLayout
from PySide6.QtCore import Qt
from localization import strings
from theme.layout_constants import (
    BAR_HEIGHT, NAV_BUTTON_WIDTH, BUTTON_SIZE,
    BAR_CONTENTS_MARGINS, BAR_SPACING, NAV_SPACER_MIN_WIDTH, NAV_SPACER_MAX_WIDTH,
    LAYOUT_MARGINS, LAYOUT_SPACING
)
from app.widgets import IconButton, DictTextBrowser
from utils.scroll_manager import ScrollManager
from theme.widget_styles import ENTRY_STYLESHEET, FLAT_BUTTON_STYLE
from utils.constants import CROSS_MARKER, BACK_ARROW, FORWARD_ARROW


def same_senses(a, b):
    return list(a or ()) == list(b or ())


class NavigationBar(QWidget):
    def __init__(self, parent, open_callback):
        super().__init__(parent)
        self.open_callback = open_callback
        self.navigation_stack = []
        self.current_index = -1

        self.setVisible(False)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setFixedHeight(BAR_HEIGHT)

        layout = QHBoxLayout()
        layout.setContentsMargins(*BAR_CONTENTS_MARGINS)
        layout.setSpacing(BAR_SPACING)

        self.back_button = QPushButton(f"{BACK_ARROW} {strings.button.back}")
        self.back_button.setCursor(Qt.PointingHandCursor)
        self.back_button.setFlat(True)
        self.back_button.setStyleSheet(FLAT_BUTTON_STYLE)
        self.back_button.setFixedWidth(NAV_BUTTON_WIDTH)
        self.back_button.clicked.connect(self.on_back)

        self.back_spacer = QWidget()
        self.back_spacer.setFixedWidth(NAV_BUTTON_WIDTH)
        self.back_spacer.setVisible(False)

        self.button_spacer = QWidget()
        self.button_spacer.setMinimumWidth(NAV_SPACER_MIN_WIDTH)
        self.button_spacer.setMaximumWidth(NAV_SPACER_MAX_WIDTH)
        self.button_spacer.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Fixed)

        self.forward_button = QPushButton(f"{FORWARD_ARROW} {strings.button.forward}")
        self.forward_button.setCursor(Qt.PointingHandCursor)
        self.forward_button.setFlat(True)
        self.forward_button.setStyleSheet(FLAT_BUTTON_STYLE)
        self.forward_button.setFixedWidth(NAV_BUTTON_WIDTH)
        self.forward_button.clicked.connect(self.on_forward)

        self.close_button = IconButton(CROSS_MARKER, flat=True)
        self.close_button.setFixedSize(BUTTON_SIZE)
        self.close_button.clicked.connect(self.hide)

        layout.addWidget(self.back_button)
        layout.addWidget(self.back_spacer)
        layout.addWidget(self.button_spacer)
        layout.addWidget(self.forward_button)
        layout.addStretch()
        layout.addWidget(self.close_button)

        self.setLayout(layout)

    def update_buttons(self):
        back_visible = self.current_index > 0
        self.back_button.setVisible(back_visible)
        self.back_spacer.setVisible(not back_visible)
        self.forward_button.setVisible(self.current_index < len(self.navigation_stack) - 1)

    def on_back(self):
        if self.current_index > 0:
            self.current_index -= 1
            entry = self.navigation_stack[self.current_index]
            self.open_callback(entry['headword'], entry['sense_parts'],
                               entry.get('entry_row_id'), entry.get('target'))
            self.update_buttons()

    def on_forward(self):
        if self.current_index < len(self.navigation_stack) - 1:
            self.current_index += 1
            entry = self.navigation_stack[self.current_index]
            self.open_callback(entry['headword'], entry['sense_parts'],
                               entry.get('entry_row_id'), entry.get('target'))
            self.update_buttons()

    def push(self, headword, sense_parts, old_headword, entry_row_id=None, old_row_id=None,
             target=None, old_target=None, old_senses=None):
        if headword == old_headword and entry_row_id == old_row_id \
                and target == old_target and same_senses(sense_parts, old_senses):
            return

        stack = self.navigation_stack[:self.current_index + 1]

        # The tip must be the entry we are actually leaving. It can be stale:
        # opening an entry from the search results calls display_entry()
        # directly, so push() never runs and the tip is left behind.
        tip = stack[-1] if stack else None
        if tip is None or tip['headword'] != old_headword \
                or tip.get('entry_row_id') != old_row_id \
                or not same_senses(tip.get('sense_parts'), old_senses):
            stack = [] if old_headword is None else stack + [{
                'headword': old_headword, 'sense_parts': old_senses, 'entry_row_id': old_row_id,
                'target': old_target,
            }]

        stack.append({'headword': headword, 'sense_parts': sense_parts,
                      'entry_row_id': entry_row_id, 'target': target})
        self.navigation_stack = stack
        self.current_index = len(stack) - 1
        self.setVisible(len(self.navigation_stack) > 1)
        self.update_buttons()

    def clear(self):
        self.navigation_stack = []
        self.current_index = -1
        self.setVisible(False)
        self.update_buttons()


class EntryViewer:
    def __init__(self, main_window, open_entry_callback):
        self.container = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(*LAYOUT_MARGINS)
        layout.setSpacing(LAYOUT_SPACING)

        self.navigation_bar = NavigationBar(main_window, open_entry_callback)
        layout.addWidget(self.navigation_bar)

        self.viewer = DictTextBrowser()
        self.viewer.setReadOnly(True)
        self.viewer.setOpenExternalLinks(False)
        self.viewer.setFocusPolicy(Qt.ClickFocus)
        self.viewer.anchorClicked.connect(main_window.on_link_clicked)
        self.viewer.document().setDefaultStyleSheet(ENTRY_STYLESHEET)

        layout.addWidget(self.viewer)
        self.container.setLayout(layout)

        self.scroll_manager = ScrollManager(self.viewer)
        self.stored_html = None

    def get_widget(self):
        return self.container

    def get_viewer(self):
        return self.viewer

    def display_html(self, html):
        self.stored_html = html
        self.viewer.setHtml(html)

    def display_entry(self, result, formatter):
        self.stored_html = formatter.format_entry(result[2])
        self.scroll_manager.cache_scroll()
        self.viewer.setHtml(self.stored_html)
        self.scroll_manager.last_anchor = None

    def refresh(self):
        if self.stored_html:
            self.scroll_manager.restore_content(self.stored_html)

    def clear(self):
        self.viewer.clear()
        self.scroll_manager.clear_cache()

    def scroll_to_anchor(self, anchor_id):
        self.scroll_manager.scroll_to_anchor(anchor_id)
