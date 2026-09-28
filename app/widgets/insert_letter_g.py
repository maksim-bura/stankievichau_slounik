from PySide6.QtCore import Qt
from localization import strings
from app.widgets.menu_button import MenuButton


INSERT_LETTER_G = '\u0491'


class InsertLetterGButton(MenuButton):
    def __init__(self, parent=None):
        super().__init__(INSERT_LETTER_G, strings.tooltip.insert_letter_g, parent)
        self.setFocusPolicy(Qt.NoFocus)