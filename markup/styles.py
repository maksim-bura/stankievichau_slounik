from theme.widget_styles import (
    FONT_STACK, COLOR_BORDER_DEFAULT, COLOR_SELECTED_BG, COLOR_BORDER_SELECTED,
    COLOR_TOOLTIP_BG, COLOR_HOVER_BG, COLOR_BUTTON_HOVER,
    COLOR_BUTTON_PRESSED_HOVER, COLOR_MENU_PRESSED_FG,
    COLOR_CHECKED_PRESSED_FG, COLOR_CHECKED_PRESSED_BG,
    COLOR_CHECKED_PRESSED_HOVER_BG, COLOR_CHECKED_PRESSED_BORDER,
)

MARKUP_GLOBAL_STYLE = f"""
    QWidget {{
        font-family: {FONT_STACK};
        font-size: 12pt;
    }}
    QListWidget {{
        font-family: {FONT_STACK};
        font-size: 12pt;
        font-weight: bold;
    }}
    QLineEdit {{
        font-family: {FONT_STACK};
        font-size: 12pt;
        background-color: white;
        border: 1px solid {COLOR_BORDER_DEFAULT};
        border-radius: 3px;
        padding: 2px;
    }}
    QLineEdit:focus {{
        background-color: white;
    }}
    QToolTip {{
        font-family: {FONT_STACK};
        font-size: 12pt;
        background-color: {COLOR_TOOLTIP_BG};
        color: black;
        border: 1px solid {COLOR_BORDER_DEFAULT};
    }}
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

ENTRY_LIST_STYLE = f"""
    QListWidget::item {{
        border-left: 3px solid transparent;
        padding: 1px;
    }}
"""

CHECKED_TOGGLE_STYLE = f"""
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
    QPushButton[pressed="true"] {{
        background-color: {COLOR_CHECKED_PRESSED_BG};
        color: {COLOR_CHECKED_PRESSED_FG};
        border: 2px solid {COLOR_CHECKED_PRESSED_BORDER};
    }}
    QPushButton[pressed="true"]:hover {{
        background-color: {COLOR_CHECKED_PRESSED_HOVER_BG};
    }}
    QPushButton[pressed="menu"] {{
        background-color: {COLOR_SELECTED_BG};
        color: {COLOR_MENU_PRESSED_FG};
        border: 2px solid {COLOR_BORDER_SELECTED};
    }}
    QPushButton[pressed="menu"]:hover {{
        background-color: {COLOR_BUTTON_PRESSED_HOVER};
    }}
"""

REBUILD_BUTTON_STYLE = f"""
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
    QPushButton:pressed {{
        background-color: {COLOR_SELECTED_BG};
        color: {COLOR_MENU_PRESSED_FG};
        border: 2px solid {COLOR_BORDER_SELECTED};
    }}
    QPushButton:pressed:hover {{
        background-color: {COLOR_BUTTON_PRESSED_HOVER};
    }}
"""

TAG_BUTTON_STYLE = f"""
    QPushButton {{
        border: none;
        background-color: transparent;
        color: black;
        padding: 2px 6px;
    }}
    QPushButton:hover {{
        color: {COLOR_BORDER_SELECTED};
    }}
"""