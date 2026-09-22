from PySide6.QtCore import Qt, QPoint, QRect, Signal
from PySide6.QtGui import QCursor, QFont
from PySide6.QtWidgets import QPushButton, QSizePolicy, QMenu, QWidgetAction, QLabel, QWidget, QHBoxLayout, QVBoxLayout
from localization import strings
from theme.layout_constants import BUTTON_SIZE, SEARCH_BOX_HEIGHT, MENU_OPTION_MARGINS, MENU_INDENT_MARGINS
from theme.widget_styles import MENU_BUTTON_STYLE, COLOR_DISABLED_FG
from utils.constants import CHECK_MARK, CHECK_BLANK, RADIO_ON, RADIO_OFF, GEAR_MARKER


class _ToggleOption(QWidget):
    def __init__(self, text, glyph_checked, glyph_unchecked, checked=False, parent=None):
        super().__init__(parent)
        self._checked = checked
        self._text = text
        self._glyph_checked = glyph_checked
        self._glyph_unchecked = glyph_unchecked
        self._label = QLabel(self)
        layout = QHBoxLayout(self)
        layout.addWidget(self._label)
        self.setMinimumHeight(SEARCH_BOX_HEIGHT)
        layout.setContentsMargins(*MENU_OPTION_MARGINS)
        self._update_display()

    def _update_display(self):
        prefix = self._glyph_checked if self._checked else self._glyph_unchecked
        self._label.setText(f'{prefix} {self._text}')

    def set_checked(self, checked):
        self._checked = checked
        self._update_display()

    def is_checked(self):
        return self._checked

    def mouseReleaseEvent(self, event):
        event.accept()


class _CheckOption(_ToggleOption):
    clicked = Signal(object)

    def __init__(self, text, checked=False, parent=None):
        self._active = True
        super().__init__(text, CHECK_MARK, CHECK_BLANK, checked, parent)
        self._update_display()

    def _update_display(self):
        super()._update_display()
        if not self._active:
            self._label.setStyleSheet(f'color: {COLOR_DISABLED_FG};')
        else:
            self._label.setStyleSheet('')

    def set_active(self, active):
        self._active = active
        self._update_display()

    def mousePressEvent(self, event):
        event.accept()
        if self._active:
            self._checked = not self._checked
            self._update_display()
            self.clicked.emit(self)


class _RadioOption(_ToggleOption):
    toggled = Signal(object)

    def __init__(self, text, checked=False, parent=None):
        super().__init__(text, RADIO_ON, RADIO_OFF, checked, parent)

    def mousePressEvent(self, event):
        event.accept()
        if not self._checked:
            self._checked = True
            self._update_display()
            self.toggled.emit(self)


class SettingsButton(QPushButton):
    search_mode_changed = Signal()

    def __init__(self, sources_button=None, parent=None):
        super().__init__(GEAR_MARKER, parent)
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
        heading_label.setContentsMargins(*MENU_OPTION_MARGINS)
        font = QFont()
        font.setBold(True)
        heading_label.setFont(font)
        heading_action.setDefaultWidget(heading_label)
        self.settings_menu.addAction(heading_action)
        self.settings_menu.addSeparator()

        belarusian_data = strings.settings.search_settings.search_in_belarusian
        russian_label = strings.settings.search_settings.search_in_russian

        self._belarusian_radio = _RadioOption(belarusian_data.label, checked=True)
        self._belarusian_radio.toggled.connect(self._on_radio_toggled)
        self._belarusian_radio_action = QWidgetAction(self.settings_menu)
        self._belarusian_radio_action.setDefaultWidget(self._belarusian_radio)
        self.settings_menu.addAction(self._belarusian_radio_action)

        self._russian_radio = _RadioOption(russian_label)
        self._russian_radio.toggled.connect(self._on_radio_toggled)
        self._russian_radio_action = QWidgetAction(self.settings_menu)
        self._russian_radio_action.setDefaultWidget(self._russian_radio)
        self.settings_menu.addAction(self._russian_radio_action)

        self._scope_actions = []
        self._add_scope_option(belarusian_data.headwords, checked=True)
        self._add_scope_option(belarusian_data.examples, checked=True)

        self.settings_menu.aboutToHide.connect(self._on_menu_closed)
        self.clicked.connect(self._on_clicked)

    def _add_scope_option(self, text, checked=False):
        option = _CheckOption(text, checked)
        option.layout().setContentsMargins(*MENU_INDENT_MARGINS)
        option.clicked.connect(self._on_sub_option_clicked)
        action = QWidgetAction(self.settings_menu)
        action.setDefaultWidget(option)
        self.settings_menu.insertAction(self._russian_radio_action, action)
        self._scope_actions.append((option, action))

    def _headwords_option(self):
        return self._scope_actions[0][0]

    def _examples_option(self):
        return self._scope_actions[1][0]

    def _all_scope_options(self):
        return [option for option, _ in self._scope_actions]

    def _all_scope_actions(self):
        return [action for _, action in self._scope_actions]

    def get_option_states(self):
        if self._russian_radio.is_checked():
            return {
                'search_in_headwords': False,
                'search_in_translations': True,
                'search_in_examples': False,
            }
        else:
            return {
                'search_in_headwords': self._headwords_option().is_checked(),
                'search_in_translations': False,
                'search_in_examples': self._examples_option().is_checked(),
            }

    def _on_radio_toggled(self, radio):
        if radio is self._belarusian_radio:
            self._russian_radio.set_checked(False)
        else:
            self._belarusian_radio.set_checked(False)
        self._update_sub_visibility()
        self.search_mode_changed.emit()

    def _update_sub_visibility(self):
        visible = self._belarusian_radio.is_checked()
        for action in self._all_scope_actions():
            if visible:
                if action not in self.settings_menu.actions():
                    self.settings_menu.insertAction(self._russian_radio_action, action)
            else:
                self.settings_menu.removeAction(action)

    def _sync_sub_options(self):
        options = self._all_scope_options()
        checked_count = sum(o.is_checked() for o in options)
        for o in options:
            o.set_active(not (checked_count == 1 and o.is_checked()))

    def _on_sub_option_clicked(self, option):
        checked_count = sum(o.is_checked() for o in self._all_scope_options())
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