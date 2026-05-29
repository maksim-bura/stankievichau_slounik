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
from theme.widget_styles import ENTRY_STYLESHEET


class NavigationBar(QWidget):
    def __init__(self, parent, open_callback):
        super().__init__(parent)
        self.parent_window = parent
        self.open_callback = open_callback
        self.navigation_stack = []
        self.current_index = -1

        self.setVisible(False)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setFixedHeight(BAR_HEIGHT)

        layout = QHBoxLayout()
        layout.setContentsMargins(*BAR_CONTENTS_MARGINS)
        layout.setSpacing(BAR_SPACING)

        button_style = """
            QPushButton {
                border: none;
                background-color: transparent;
                color: black;
                padding: 0px;
            }
        """

        self.back_button = QPushButton(f"\u2b05\ufe0f {strings.button.back}")
        self.back_button.setCursor(Qt.PointingHandCursor)
        self.back_button.setFlat(True)
        self.back_button.setStyleSheet(button_style)
        self.back_button.setFixedWidth(NAV_BUTTON_WIDTH)
        self.back_button.clicked.connect(self.on_back)

        self.back_spacer = QWidget()
        self.back_spacer.setFixedWidth(NAV_BUTTON_WIDTH)
        self.back_spacer.setVisible(False)

        self.button_spacer = QWidget()
        self.button_spacer.setMinimumWidth(NAV_SPACER_MIN_WIDTH)
        self.button_spacer.setMaximumWidth(NAV_SPACER_MAX_WIDTH)
        self.button_spacer.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Fixed)

        self.forward_button = QPushButton(f"\u27a1\ufe0f {strings.button.forward}")
        self.forward_button.setCursor(Qt.PointingHandCursor)
        self.forward_button.setFlat(True)
        self.forward_button.setStyleSheet(button_style)
        self.forward_button.setFixedWidth(NAV_BUTTON_WIDTH)
        self.forward_button.clicked.connect(self.on_forward)

        self.close_button = IconButton("\u274c", flat=True)
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
            self.open_callback(self.navigation_stack[self.current_index]['headword'],
                              self.navigation_stack[self.current_index]['sense_parts'])
            self.update_buttons()

    def on_forward(self):
        if self.current_index < len(self.navigation_stack) - 1:
            self.current_index += 1
            self.open_callback(self.navigation_stack[self.current_index]['headword'],
                              self.navigation_stack[self.current_index]['sense_parts'])
            self.update_buttons()

    def push(self, headword, sense_parts, old_headword):
        if headword == old_headword:
            return

        if self.current_index < len(self.navigation_stack) - 1:
            self.navigation_stack = self.navigation_stack[:self.current_index + 1]

        if not self.navigation_stack and old_headword is not None:
            self.navigation_stack.append({'headword': old_headword, 'sense_parts': None})
            self.current_index = 0

        self.navigation_stack.append({'headword': headword, 'sense_parts': sense_parts})
        self.current_index = len(self.navigation_stack) - 1
        self.setVisible(len(self.navigation_stack) > 1)
        self.update_buttons()

    def clear(self):
        self.navigation_stack = []
        self.current_index = -1
        self.setVisible(False)
        self.update_buttons()


class EntryViewer:
    def __init__(self, parent_window, open_entry_callback):
        self.parent = parent_window
        self.open_entry_callback = open_entry_callback

        self.container = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(*LAYOUT_MARGINS)
        layout.setSpacing(LAYOUT_SPACING)

        self.navigation_bar = NavigationBar(parent_window, open_entry_callback)
        layout.addWidget(self.navigation_bar)

        self.viewer = DictTextBrowser()
        self.viewer.setReadOnly(True)
        self.viewer.setOpenExternalLinks(False)
        self.viewer.setFocusPolicy(Qt.NoFocus)
        self.viewer.anchorClicked.connect(parent_window.on_link_clicked)
        self.viewer.document().setDefaultStyleSheet(ENTRY_STYLESHEET)

        layout.addWidget(self.viewer)
        self.container.setLayout(layout)

        self.scroll_manager = ScrollManager(self.viewer)
        self.stored_html = None

    def get_widget(self):
        return self.container

    def get_viewer(self):
        return self.viewer

    def display_entry(self, result, formatter):
        self.stored_html = formatter.format_entry(result[2])
        self.scroll_manager.cache_state()
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

    def cache_scroll(self):
        self.scroll_manager.cache_state()

    def restore_scroll(self):
        self.scroll_manager.restore_state()
