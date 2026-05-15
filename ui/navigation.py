from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QSizePolicy
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from localization import strings
from .components.constants import (
    NAV_BAR_HEIGHT, NAV_BAR_MIN_WIDTH, NAV_BUTTON_WIDTH, CLOSE_BUTTON_SIZE,
    NAV_BAR_CONTENTS_MARGINS, NAV_BAR_BACKGROUND, NAV_SPACER_MIN_WIDTH, NAV_SPACER_MAX_WIDTH
)
from .components.widgets import IconButton


class NavigationBar(QWidget):
    def __init__(self, parent, open_callback):
        super().__init__(parent)
        self.parent_window = parent
        self.open_callback = open_callback
        self.navigation_stack = []
        self.current_index = -1

        self.setVisible(False)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setFixedHeight(NAV_BAR_HEIGHT)
        self.setMinimumWidth(NAV_BAR_MIN_WIDTH)
        self.setAutoFillBackground(True)

        palette = self.palette()
        palette.setColor(self.backgroundRole(), QColor(*NAV_BAR_BACKGROUND))
        self.setPalette(palette)
        self.setAutoFillBackground(True)

        layout = QHBoxLayout()
        layout.setContentsMargins(*NAV_BAR_CONTENTS_MARGINS)
        layout.setSpacing(0)

        button_style = """
            QPushButton {
                border: none;
                background-color: transparent;
                color: black;
                padding: 0px;
            }
        """

        self.back_button = QPushButton(f"⬅️ {strings.back_button}")
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

        self.forward_button = QPushButton(f"➡️ {strings.forward_button}")
        self.forward_button.setCursor(Qt.PointingHandCursor)
        self.forward_button.setFlat(True)
        self.forward_button.setStyleSheet(button_style)
        self.forward_button.setFixedWidth(NAV_BUTTON_WIDTH)
        self.forward_button.clicked.connect(self.on_forward)

        self.close_button = IconButton("❌", flat=True)
        self.close_button.setFixedSize(CLOSE_BUTTON_SIZE)
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