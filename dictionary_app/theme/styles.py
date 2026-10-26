FONT_STACK = "'Cambria', 'Times New Roman', Times, serif"

FONT_SIZE_BASE = '12pt'
FONT_SIZE_HEADING_LARGE = '16pt'
FONT_SIZE_HEADING_MEDIUM = '14pt'

BORDER_WIDTH_THIN = '1px'
BORDER_WIDTH_THICK = '2px'
BORDER_WIDTH_ACCENT = '3px'
BORDER_RADIUS_SMALL = '3px'
BORDER_RADIUS_MEDIUM = '5px'

PADDING_NONE = '0px'
PADDING_THIN = '2px'
PADDING_MEDIUM = '5px'

COLOR_BORDER_DEFAULT = '#c0c0c0'
COLOR_NORMAL_BG = '#ffffff'
COLOR_HOVER_BG = '#fafafa'
COLOR_SELECTED_BG = '#edf7fd'
COLOR_BORDER_SELECTED = '#7c9ec0'
COLOR_HIGHLIGHT_BG = '#FFF9C4'
COLOR_TOOLTIP_BG = '#ffffcc'
COLOR_DISABLED_FG = '#888888'
COLOR_MENU_PRESSED_FG = '#1e3a5f'
COLOR_BUTTON_HOVER = '#ececec'
COLOR_BUTTON_PRESSED_HOVER = '#e0eefb'


def font_rule(widget, size=FONT_SIZE_BASE):
    return (f"    {widget} {{\n"
            f"    font-family: {FONT_STACK};\n"
            f"    font-size: {size};\n"
            f"    }}\n")


LINEEDIT_RULE = f"""
    QLineEdit {{
        background-color: white;
        border: {BORDER_WIDTH_THIN} solid {COLOR_BORDER_DEFAULT};
        border-radius: {BORDER_RADIUS_SMALL};
        padding: {PADDING_THIN};
    }}
    QLineEdit:focus {{
        background-color: white;
    }}
"""

TOOLTIP_RULE = f"""
    QToolTip {{
        font-family: {FONT_STACK};
        font-size: {FONT_SIZE_BASE};
        background-color: {COLOR_TOOLTIP_BG};
        color: black;
        border: {BORDER_WIDTH_THIN} solid {COLOR_BORDER_DEFAULT};
    }}
"""

BOLD_LIST_STYLE = (
    font_rule('QListWidget') + "    QListWidget {\n    font-weight: bold;\n    }\n" +
    font_rule('QListView') + "    QListView {\n    font-weight: bold;\n    }\n"
)

GLOBAL_STYLE = (
    font_rule('QWidget') +
    BOLD_LIST_STYLE +
    font_rule('QLineEdit') + LINEEDIT_RULE +
    TOOLTIP_RULE
)


def flat_button_style(padding=PADDING_NONE, declarations='', hover=''):
    style = (f"    QPushButton {{\n"
             f"        border: none;\n"
             f"        background-color: transparent;\n"
             f"        color: black;\n"
             f"        padding: {padding};\n"
             f"{declarations}"
             f"    }}\n")
    if hover:
        style += hover
    return style


FLAT_BUTTON_STYLE = flat_button_style()

SEARCH_BOX_STYLE = LINEEDIT_RULE

MENU_BUTTON_STYLE = f"""
    QPushButton[class="menu-button"] {{
        background-color: {COLOR_HOVER_BG};
        color: black;
        font-weight: bold;
        border: {BORDER_WIDTH_THICK} solid {COLOR_BORDER_DEFAULT};
        border-radius: {BORDER_RADIUS_MEDIUM};
        padding: {PADDING_MEDIUM};
        font-family: {FONT_STACK};
        font-size: {FONT_SIZE_BASE};
    }}
    QPushButton[class="menu-button"]:hover {{
        background-color: {COLOR_BUTTON_HOVER};
    }}
    QPushButton[class="menu-button"][pressed="true"],
    QPushButton[class="menu-button"][pressed="true"][dual="true"],
    QPushButton[class="menu-button"][pressed="menu"] {{
        background-color: {COLOR_SELECTED_BG};
        color: {COLOR_MENU_PRESSED_FG};
        border: {BORDER_WIDTH_THICK} solid {COLOR_BORDER_SELECTED};
    }}
    QPushButton[class="menu-button"][pressed="true"]:hover,
    QPushButton[class="menu-button"][pressed="true"][dual="true"]:hover,
    QPushButton[class="menu-button"][pressed="menu"]:hover {{
        background-color: {COLOR_BUTTON_PRESSED_HOVER};
    }}
"""

RESULTS_LIST_STYLE = f"""
    QListView::item {{
        border-left: {BORDER_WIDTH_ACCENT} solid transparent;
    }}
    QListView::item:hover {{
        border-left: {BORDER_WIDTH_ACCENT} solid {COLOR_BORDER_DEFAULT};
        background: {COLOR_HOVER_BG};
        color: black;
    }}
    QListView::item:selected {{
        border-left: {BORDER_WIDTH_ACCENT} solid {COLOR_BORDER_SELECTED};
        background: {COLOR_SELECTED_BG};
        color: black;
    }}
    QListView::item:selected:!active {{
        border-left: {BORDER_WIDTH_ACCENT} solid {COLOR_BORDER_SELECTED};
        background: {COLOR_SELECTED_BG};
        color: black;
    }}
"""

ENTRY_STYLESHEET = f"""
    body {{
        font-family: {FONT_STACK};
        font-size: {FONT_SIZE_BASE};
        line-height: 1.4;
        margin: 0;
        text-align: justify;
    }}
    .hw {{ font-weight: bold; font-style: normal; }}
    .g, .ex {{ font-style: italic; }}
    .i {{ font-style: italic; font-weight: normal; }}
    .st {{ font-style: italic; }}
    .t {{ font-style: normal; }}

    .b, .n {{ font-weight: bold; }}
    .abbr {{ font-weight: bold; }}
    .see {{ font-style: italic; }}
    .p {{ font-style: normal; font-weight: normal; }}
    .h1 {{ font-weight: bold; font-size: {FONT_SIZE_HEADING_LARGE}; }}
    .h2 {{ font-weight: bold; font-size: {FONT_SIZE_HEADING_MEDIUM}; }}

    .sense {{ font-style: normal; }}
    .headword-arrow {{ font-weight: normal; margin-right: 4px; font-style: normal; }}
    .sense-arrow {{ font-weight: normal; margin-right: 4px; font-style: normal; }}
    .link, .word-link {{
        font-style: italic; color: inherit;
        text-decoration: none; cursor: pointer;
    }}
    .link:visited, .word-link:visited, .source-link:visited {{
        text-decoration: none; color: inherit;
    }}
    .link:hover, .word-link:hover {{ text-decoration: underline; }}
    .src, .source-link {{ font-style: normal; }}
    .source-link {{ font-style: normal; color: inherit; text-decoration: none; cursor: pointer; }}
    .st-link {{ font-style: italic; }}
    .source-link:hover {{ text-decoration: underline; }}
    .search-highlight {{ background-color: {COLOR_HIGHLIGHT_BG}; }}
    a, a:visited {{ text-decoration: none; color: inherit; }}
    a:hover {{ text-decoration: underline; }}
    .toggle-btn, .toggle-btn:visited, .toggle-btn:hover {{
        text-decoration: none; color: inherit; cursor: pointer;
    }}
"""
