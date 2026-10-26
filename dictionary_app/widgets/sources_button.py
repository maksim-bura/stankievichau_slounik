from dictionary_app.localization import strings
from dictionary_app.widgets.menu_button import MenuButton
from dictionary_app.utils.constants import BOOKS_MARKER


class SourcesButton(MenuButton):
    def __init__(self, parent=None):
        super().__init__(BOOKS_MARKER, strings.app_buttons.sources.tooltip, parent, emoji_font=True)
        self.sources_visible = False
        self.update_style()

    def update_style(self):
        if self.sources_visible:
            self.setProperty("pressed", "true")
        else:
            self.setProperty("pressed", "false")
        self.style().unpolish(self)
        self.style().polish(self)

    def set_sources_visible(self, visible):
        self.sources_visible = visible
        self.update_style()