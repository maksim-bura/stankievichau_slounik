from PySide6.QtCore import Qt
from dictionary_app.localization import strings
from dictionary_app.widgets.menu_button import MenuButton


INSERT_LETTER_G = '\u0491'


class InsertLetterGButton(MenuButton):
    def __init__(self, parent=None):
        super().__init__(INSERT_LETTER_G, strings.app_buttons.insert_g.tooltip, parent)
        self.setFocusPolicy(Qt.NoFocus)