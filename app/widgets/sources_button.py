from PySide6.QtWidgets import QPushButton, QSizePolicy
from PySide6.QtCore import Qt
from localization import strings
from theme.layout_constants import BUTTON_SIZE
from theme.widget_styles import MENU_BUTTON_STYLE


class SourcesButton(QPushButton):
    def __init__(self, parent=None):
        super().__init__("📚", parent)
        self.sources_visible = False
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.setFixedSize(BUTTON_SIZE)
        self.setCursor(Qt.PointingHandCursor)
        self.setProperty("class", "menu-button")
        self.setToolTip(strings.tooltip.sources)
        self.setStyleSheet(MENU_BUTTON_STYLE)
        self.update_style()

    def update_style(self):
        if self.sources_visible:
            self.setProperty("pressed", "true")
        else:
            self.setProperty("pressed", "false")
        self.style().unpolish(self)
        self.style().polish(self)

    def toggle(self):
        self.sources_visible = not self.sources_visible
        self.update_style()
        return self.sources_visible

    def set_sources_visible(self, visible):
        self.sources_visible = visible
        self.update_style()
