from dictionary_app.theme.widget_styles import (
    FONT_STACK, COLOR_NORMAL_BG, COLOR_BORDER_DEFAULT, COLOR_SELECTED_BG,
    COLOR_BORDER_SELECTED, COLOR_HOVER_BG, COLOR_BUTTON_HOVER,
    COLOR_BUTTON_PRESSED_HOVER, COLOR_MENU_PRESSED_FG,
    LINEEDIT_RULE, TOOLTIP_RULE, BOLD_LIST_STYLE, flat_button_style, font_rule,
)

_MARKUP_TAB_STYLE = f"""
    QTabWidget::pane {{
        border-top: 1px solid {COLOR_BORDER_DEFAULT};
    }}
    QTabBar::tab {{
        padding: 4px 12px;
        margin-right: 2px;
        background-color: {COLOR_HOVER_BG};
        border: 2px solid {COLOR_BORDER_DEFAULT};
        border-radius: 5px;
    }}
    QTabBar::tab:hover {{
        background-color: {COLOR_BUTTON_HOVER};
    }}
    QTabBar::tab:selected {{
        background-color: {COLOR_SELECTED_BG};
        color: {COLOR_MENU_PRESSED_FG};
        border: 2px solid {COLOR_BORDER_SELECTED};
    }}
"""

MARKUP_GLOBAL_STYLE = (
    font_rule('QWidget')
    + BOLD_LIST_STYLE
    + font_rule('QLineEdit')
    + LINEEDIT_RULE
    + TOOLTIP_RULE
    + _MARKUP_TAB_STYLE
)

ENTRY_LIST_STYLE = f"""
    QListView::item {{
        border-left: 3px solid transparent;
        padding: 1px;
    }}
"""

ATTRIBUTE_POPUP_STYLE = f"""
    QListWidget {{
        background-color: {COLOR_NORMAL_BG};
        border: 1px solid {COLOR_BORDER_DEFAULT};
        border-radius: 5px;
        padding: 2px 0;
        outline: 0;
        font-family: {FONT_STACK};
        font-size: 12pt;
    }}
    QListWidget::item {{
        padding: 2px 10px;
        border-left: 3px solid transparent;
        color: black;
    }}
    QListWidget::item:hover {{
        background: {COLOR_HOVER_BG};
        border-left: 3px solid {COLOR_BORDER_DEFAULT};
        color: black;
    }}
    QListWidget::item:selected {{
        background: {COLOR_SELECTED_BG};
        border-left: 3px solid {COLOR_BORDER_SELECTED};
        color: black;
    }}
    QListWidget::item:selected:!active {{
        background: {COLOR_SELECTED_BG};
        border-left: 3px solid {COLOR_BORDER_SELECTED};
        color: black;
    }}
"""

_TOGGLE_BUTTON_BASE = f"""
    QPushButton {{
        background-color: {COLOR_HOVER_BG};
        color: black;
        font-weight: bold;
        border: 2px solid {COLOR_BORDER_DEFAULT};
        border-radius: 5px;
        padding: 5px;
        font-family: {FONT_STACK};
        font-size: 12pt;
    }}
    QPushButton:hover {{
        background-color: {COLOR_BUTTON_HOVER};
    }}
"""

ENTRY_CHECKED_TOGGLE_STYLE = flat_button_style(
    padding='2px 6px',
    declarations=(
        f"        font-family: {FONT_STACK};\n"
        f"        font-size: 12pt;\n"
    ),
)

REBUILD_BUTTON_STYLE = _TOGGLE_BUTTON_BASE + f"""
    QPushButton:pressed {{
        background-color: {COLOR_SELECTED_BG};
        color: {COLOR_MENU_PRESSED_FG};
        border: 2px solid {COLOR_BORDER_SELECTED};
    }}
    QPushButton:pressed:hover {{
        background-color: {COLOR_BUTTON_PRESSED_HOVER};
    }}
"""

TAG_BUTTON_STYLE = flat_button_style(
    padding='2px 6px',
    hover=(
        f"    QPushButton:hover {{\n"
        f"        color: {COLOR_BORDER_SELECTED};\n"
        f"    }}\n"
    ),
)
