from PySide6.QtCore import Qt, QPoint, QRect, Signal
from PySide6.QtGui import QCursor, QFont
from PySide6.QtWidgets import QPushButton, QSizePolicy, QMenu, QWidgetAction, QLabel, QWidget, QHBoxLayout, QVBoxLayout
from localization import strings
from theme.layout_constants import BUTTON_SIZE, SEARCH_BOX_HEIGHT
from theme.widget_styles import MENU_BUTTON_STYLE


class _CheckOption(QWidget):
    clicked = Signal(object)

    def __init__(self, text, checked=False, parent=None):
        super().__init__(parent)
        self._checked = checked
        self._active = True
        self._text = text
        self._label = QLabel(self)
        layout = QHBoxLayout(self)
        layout.addWidget(self._label)
        self.setMinimumHeight(SEARCH_BOX_HEIGHT)
        layout.setContentsMargins(6, 9, 6, 9)
        self._update_display()

    def _update_display(self):
        prefix = '\u2705' if self._checked else '\u2b1c'
        self._label.setText(f'{prefix} {self._text}')
        if not self._active:
            self._label.setStyleSheet('color: #888888;')
        else:
            self._label.setStyleSheet('')

    def set_checked(self, checked):
        self._checked = checked
        self._update_display()

    def set_active(self, active):
        self._active = active
        self._update_display()

    def is_checked(self):
        return self._checked

    def mousePressEvent(self, event):
        event.accept()
        if self._active:
            self._checked = not self._checked
            self._update_display()
            self.clicked.emit(self)

    def mouseReleaseEvent(self, event):
        event.accept()


class _RadioOption(QWidget):
    toggled = Signal(object)

    def __init__(self, text, checked=False, parent=None):
        super().__init__(parent)
        self._checked = checked
        self._text = text
        self._label = QLabel(self)
        layout = QHBoxLayout(self)
        layout.addWidget(self._label)
        self.setMinimumHeight(SEARCH_BOX_HEIGHT)
        layout.setContentsMargins(6, 9, 6, 9)
        self._update_display()

    def _update_display(self):
        prefix = '\U0001f7e2' if self._checked else '\u26aa'
        self._label.setText(f'{prefix} {self._text}')

    def set_checked(self, checked):
        self._checked = checked
        self._update_display()

    def is_checked(self):
        return self._checked

    def mousePressEvent(self, event):
        event.accept()
        if not self._checked:
            self._checked = True
            self._update_display()
            self.toggled.emit(self)

    def mouseReleaseEvent(self, event):
        event.accept()


class SettingsButton(QPushButton):
    search_mode_changed = Signal()

    def __init__(self, sources_button=None, parent=None):
        super().__init__("\u2699\ufe0f", parent)
        self._sources_button = sources_button
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.setFixedSize(BUTTON_SIZE)
        self.setCursor(Qt.PointingHandCursor)
        self.setProperty("class", "menu-button")
        self.setToolTip(strings.tooltip.settings)
        self.setStyleSheet(MENU_BUTTON_STYLE)
        self._consume_next_press = False

        self.settings_menu = QMenu(self)
        heading_action = QWidgetAction(self.settings_menu)
        heading_label = QLabel(strings.settings.search_settings.heading)
        heading_label.setContentsMargins(6, 9, 6, 9)
        font = QFont()
        font.setBold(True)
        heading_label.setFont(font)
        heading_action.setDefaultWidget(heading_label)
        self.settings_menu.addAction(heading_action)
        self.settings_menu.addSeparator()

        be_data = strings.settings.search_settings.search_in_belarusian
        ru_label = strings.settings.search_settings.search_in_russian

        self._radio1 = _RadioOption(be_data.label, checked=True)
        self._radio1.toggled.connect(self._on_radio_toggled)
        self._radio1_action = QWidgetAction(self.settings_menu)
        self._radio1_action.setDefaultWidget(self._radio1)
        self.settings_menu.addAction(self._radio1_action)

        self._radio2 = _RadioOption(ru_label)
        self._radio2.toggled.connect(self._on_radio_toggled)
        self._radio2_action = QWidgetAction(self.settings_menu)
        self._radio2_action.setDefaultWidget(self._radio2)
        self.settings_menu.addAction(self._radio2_action)

        self._sub_options = []
        self._sub_actions = []
        self._add_sub_option(be_data.headwords, checked=True)
        self._add_sub_option(be_data.examples, checked=True)

        self.settings_menu.aboutToHide.connect(self._on_menu_closed)
        self.clicked.connect(self._on_clicked)

    def _add_sub_option(self, text, checked=False):
        option = _CheckOption(text, checked)
        option.layout().setContentsMargins(24, 9, 6, 9)
        option.clicked.connect(self._on_sub_option_clicked)
        action = QWidgetAction(self.settings_menu)
        action.setDefaultWidget(option)
        self.settings_menu.insertAction(self._radio2_action, action)
        self._sub_options.append(option)
        self._sub_actions.append(action)

    def get_option_states(self):
        if self._radio2.is_checked():
            return {
                'search_in_headwords': False,
                'search_in_translations': True,
                'search_in_examples': False,
            }
        else:
            return {
                'search_in_headwords': self._sub_options[0].is_checked(),
                'search_in_translations': False,
                'search_in_examples': self._sub_options[1].is_checked(),
            }

    def _on_radio_toggled(self, radio):
        if radio is self._radio1:
            self._radio2.set_checked(False)
        else:
            self._radio1.set_checked(False)
        self._update_sub_visibility()
        self.search_mode_changed.emit()

    def _update_sub_visibility(self):
        visible = self._radio1.is_checked()
        for action in self._sub_actions:
            if visible:
                if action not in self.settings_menu.actions():
                    self.settings_menu.insertAction(self._radio2_action, action)
            else:
                self.settings_menu.removeAction(action)

    def _sync_sub_options(self):
        checked_count = sum(o.is_checked() for o in self._sub_options)
        for o in self._sub_options:
            o.set_active(not (checked_count == 1 and o.is_checked()))

    def _on_sub_option_clicked(self, option):
        checked_count = sum(o.is_checked() for o in self._sub_options)
        if checked_count == 0:
            option.set_checked(True)
        self._sync_sub_options()
        self.search_mode_changed.emit()

    def update_style(self):
        self.style().unpolish(self)
        self.style().polish(self)

    def _update_dual_property(self):
        if self._sources_button:
            is_dual = self._sources_button.property("pressed") == "true"
            self.setProperty("dual", "true" if is_dual else "false")
            self._sources_button.setProperty("dual", "true" if is_dual else "false")
            self._sources_button.update_style()
        else:
            self.setProperty("dual", "false")

    def _on_menu_closed(self):
        btn_rect = QRect(self.mapToGlobal(QPoint(0, 0)), self.size())
        self._consume_next_press = btn_rect.contains(QCursor.pos())
        self.setProperty("pressed", "false")
        self.update_style()
        if self._sources_button:
            self._sources_button.setProperty("dual", "false")
            self._sources_button.update_style()

    def mousePressEvent(self, event):
        if self._consume_next_press:
            self._consume_next_press = False
            return
        super().mousePressEvent(event)

    def _on_clicked(self):
        if self.settings_menu.isVisible():
            self.settings_menu.close()
        else:
            self._sync_sub_options()
            self._update_dual_property()
            self.setProperty("pressed", "true")
            self.update_style()
            self.settings_menu.popup(self.mapToGlobal(QPoint(0, self.height())))
