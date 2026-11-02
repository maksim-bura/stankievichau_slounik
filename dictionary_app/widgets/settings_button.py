from PySide6.QtCore import QPoint, QRect, Signal
from PySide6.QtGui import QCursor, QFont
from PySide6.QtWidgets import QMenu, QWidgetAction, QLabel
from dictionary_app.localization import strings
from dictionary_app.theme.layout_constants import MENU_OPTION_MARGINS, MENU_INDENT_MARGINS
from dictionary_app.utils.constants import GEAR_MARKER, MAGNIFIER_MARKER, ALPHABET_MARKER
from dictionary_app.utils.sort_keys import SORT_ORDER_DICTIONARY, SORT_ORDER_STANDARD
from dictionary_app.widgets.emoji_label import set_emoji_prefixed_text
from dictionary_app.widgets.menu_button import MenuButton
from dictionary_app.widgets.menu_options import CheckOption, RadioOption


PROPERTY_ON = 'true'
PROPERTY_OFF = 'false'


class SettingsButton(MenuButton):
    search_mode_changed = Signal()
    sort_order_changed = Signal()

    def __init__(self, sources_button=None, parent=None):
        super().__init__(GEAR_MARKER, strings.app_buttons.settings.tooltip, parent, emoji_font=True)
        self._sources_button = sources_button
        self._consume_next_press = False

        self.settings_menu = QMenu(self)
        self._add_heading(
            MAGNIFIER_MARKER, strings.app_buttons.settings.dropdown.title)
        self.settings_menu.addSeparator()

        belarusian_data = strings.app_buttons.settings.dropdown.search_in_belarusian
        russian_label = strings.app_buttons.settings.dropdown.search_in_russian.label

        self._belarusian_radio = RadioOption(belarusian_data.label, checked=True)
        self._belarusian_radio.toggled.connect(self._on_radio_toggled)
        self._belarusian_radio_action = self._add_option(self._belarusian_radio)

        self._scope_actions = []
        self._add_scope_option(belarusian_data.headwords, checked=True)
        self._add_scope_option(belarusian_data.examples, checked=True)

        self._russian_radio = RadioOption(russian_label)
        self._russian_radio.toggled.connect(self._on_radio_toggled)
        self._russian_radio_action = self._add_option(self._russian_radio)

        self._position_scope_options()

        self.settings_menu.addSeparator()

        alphabet_data = strings.app_buttons.settings.dropdown.alphabet_order
        self._add_heading(ALPHABET_MARKER, alphabet_data.title)
        self.settings_menu.addSeparator()
        self._standard_radio = RadioOption(alphabet_data.standard, checked=True)
        self._standard_radio.toggled.connect(self._on_alphabet_toggled)
        self._standard_radio_action = self._add_option(self._standard_radio)

        self._dictionary_radio = RadioOption(alphabet_data.dictionary)
        self._dictionary_radio.toggled.connect(self._on_alphabet_toggled)
        self._dictionary_radio_action = self._add_option(self._dictionary_radio)

        self.settings_menu.aboutToHide.connect(self._on_menu_closed)
        self.clicked.connect(self._on_clicked)

    def _add_heading(self, glyph, text):
        action = QWidgetAction(self.settings_menu)
        label = QLabel()
        label.setContentsMargins(*MENU_OPTION_MARGINS)
        font = QFont()
        font.setBold(True)
        label.setFont(font)
        set_emoji_prefixed_text(label, glyph, text)
        action.setDefaultWidget(label)
        self.settings_menu.addAction(action)
        return action

    def _add_option(self, option):
        action = QWidgetAction(self.settings_menu)
        action.setDefaultWidget(option)
        self.settings_menu.addAction(action)
        return action

    def _add_scope_option(self, text, checked=False):
        option = CheckOption(text, checked)
        option.layout().setContentsMargins(*MENU_INDENT_MARGINS)
        option.clicked.connect(self._on_sub_option_clicked)
        action = QWidgetAction(self.settings_menu)
        action.setDefaultWidget(option)
        self._scope_actions.append((option, action))

    def _position_scope_options(self):
        for _, action in self._scope_actions:
            self.settings_menu.insertAction(self._russian_radio_action, action)

    def _headwords_option(self):
        return self._scope_actions[0][0]

    def _examples_option(self):
        return self._scope_actions[1][0]

    def _all_scope_options(self):
        return [option for option, _ in self._scope_actions]

    def _all_scope_actions(self):
        return [action for _, action in self._scope_actions]

    def get_sort_order(self):
        if self._dictionary_radio.is_checked():
            return SORT_ORDER_DICTIONARY
        return SORT_ORDER_STANDARD

    def _on_alphabet_toggled(self, radio):
        if radio is self._standard_radio:
            self._dictionary_radio.set_checked(False)
        else:
            self._standard_radio.set_checked(False)
        self.sort_order_changed.emit()

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

    def _set_dynamic_property(self, widget, name, is_on):
        widget.setProperty(name, PROPERTY_ON if is_on else PROPERTY_OFF)
        widget.update_style()

    def _update_dual_property(self):
        if self._sources_button:
            is_dual = self._sources_button.property("pressed") == PROPERTY_ON
            self._set_dynamic_property(self, "dual", is_dual)
            self._set_dynamic_property(self._sources_button, "dual", is_dual)
        else:
            self._set_dynamic_property(self, "dual", False)

    def _on_menu_closed(self):
        btn_rect = QRect(self.mapToGlobal(QPoint(0, 0)), self.size())
        self._consume_next_press = btn_rect.contains(QCursor.pos())
        self._set_dynamic_property(self, "pressed", False)
        if self._sources_button:
            self._set_dynamic_property(self._sources_button, "dual", False)

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
            self._set_dynamic_property(self, "pressed", True)
            self.settings_menu.popup(self.mapToGlobal(QPoint(0, self.height())))