from dictionary_app.theme.styles import (
    COLOR_BORDER_DEFAULT, COLOR_BORDER_SELECTED, COLOR_BUTTON_HOVER, COLOR_BUTTON_PRESSED_HOVER,
    COLOR_HOVER_BG, COLOR_MENU_PRESSED_FG, COLOR_NORMAL_BG, COLOR_SELECTED_BG, FONT_STACK,
    GLOBAL_STYLE, flat_button_style
)

COLOR_D_SPAN_UNDERLINE = '#c2571a'
COLOR_AMBIGUOUS_G_BG = '#ffdab3'
COLOR_AMBIGUOUS_HW_BG = '#d8d0f2'
COLOR_CHECKED_BG = '#c8f7c5'
COLOR_CHECKED_HOVER_BG = '#b8f0b5'
COLOR_CHECKED_SELECTED_BG = '#7cbf7a'
COLOR_CHECKED_BORDER = '#a0d8a0'
COLOR_TRANSPARENT = '#00000000'
COLOR_TEXT = 'black'

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

MARKUP_GLOBAL_STYLE = GLOBAL_STYLE + _MARKUP_TAB_STYLE

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
        color: {COLOR_TEXT};
    }}
    QListWidget::item:hover {{
        background: {COLOR_HOVER_BG};
        border-left: 3px solid {COLOR_BORDER_DEFAULT};
        color: {COLOR_TEXT};
    }}
    QListWidget::item:selected {{
        background: {COLOR_SELECTED_BG};
        border-left: 3px solid {COLOR_BORDER_SELECTED};
        color: {COLOR_TEXT};
    }}
    QListWidget::item:selected:!active {{
        background: {COLOR_SELECTED_BG};
        border-left: 3px solid {COLOR_BORDER_SELECTED};
        color: {COLOR_TEXT};
    }}
"""

_TOGGLE_BUTTON_BASE = f"""
    QPushButton {{
        background-color: {COLOR_HOVER_BG};
        color: {COLOR_TEXT};
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
