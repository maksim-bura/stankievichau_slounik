from theme.widget_styles import (
    FONT_STACK, COLOR_BORDER_DEFAULT, COLOR_SELECTED_BG, COLOR_BORDER_SELECTED,
    COLOR_TOOLTIP_BG,
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
    }}
    QTabBar::tab:selected {{
        background-color: {COLOR_SELECTED_BG};
        border-bottom: 2px solid {COLOR_BORDER_SELECTED};
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
        border: none;
        background-color: transparent;
        color: black;
        padding: 0px;
    }}
    QPushButton:hover {{
        color: {COLOR_BORDER_SELECTED};
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