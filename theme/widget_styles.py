FONT_STACK = "'Cambria', 'Times New Roman', Times, serif"

COLOR_BORDER_DEFAULT = '#c0c0c0'
COLOR_NORMAL_BG = '#ffffff'
COLOR_HOVER_BG = '#fafafa'
COLOR_SELECTED_BG = '#edf7fd'
COLOR_BORDER_SELECTED = '#7c9ec0'
COLOR_HIGHLIGHT_BG = '#FFF9C4'
COLOR_TOOLTIP_BG = '#ffffcc'
COLOR_DISABLED_FG = '#888888'
COLOR_MENU_PRESSED_FG = '#1e3a5f'


def _font_rule(widget, size='12pt'):
    return (f"    {widget} {{\n"
            f"    font-family: {FONT_STACK};\n"
            f"    font-size: {size};\n"
            f"    }}\n")


GLOBAL_STYLE = (
    _font_rule('QWidget') +
    _font_rule('QListWidget') + "    QListWidget {\n    font-weight: bold;\n    }\n" +
    _font_rule('QLineEdit') +
    f"    QLineEdit {{\n"
    f"    background-color: white;\n"
    f"    border: 1px solid {COLOR_BORDER_DEFAULT};\n"
    f"    border-radius: 3px;\n"
    f"    padding: 2px;\n"
    f"    }}\n"
    "    QLineEdit:focus {\n"
    "    background-color: white;\n"
    "    }\n"
    f"    QToolTip {{\n"
    f"    font-family: {FONT_STACK};\n"
    f"    font-size: 12pt;\n"
    f"    background-color: {COLOR_TOOLTIP_BG};\n"
    f"    color: black;\n"
    f"    border: 1px solid {COLOR_BORDER_DEFAULT};\n"
    f"    }}\n"
)

FLAT_BUTTON_STYLE = f"""
    QPushButton {{
        border: none;
        background-color: transparent;
        color: black;
        padding: 0px;
    }}
"""

SEARCH_BOX_STYLE = f"""
    QLineEdit {{
        background-color: white;
        border: 1px solid {COLOR_BORDER_DEFAULT};
        border-radius: 3px;
        padding: 2px;
    }}
    QLineEdit:focus {{
        background-color: white;
    }}
"""

MENU_BUTTON_STYLE = f"""
    QPushButton[class="menu-button"] {{
        background-color: {COLOR_HOVER_BG};
        color: black;
        font-weight: bold;
        border: 2px solid {COLOR_BORDER_DEFAULT};
        border-radius: 5px;
        padding: 5px;
        font-family: {FONT_STACK};
        font-size: 12pt;
    }}
    QPushButton[class="menu-button"]:hover {{
        background-color: #ececec;
    }}
    QPushButton[class="menu-button"][pressed="true"] {{
        background-color: {COLOR_SELECTED_BG};
        color: {COLOR_MENU_PRESSED_FG};
        border: 2px solid {COLOR_BORDER_SELECTED};
    }}
    QPushButton[class="menu-button"][pressed="true"]:hover {{
        background-color: #e0eefb;
    }}
    QPushButton[class="menu-button"][pressed="true"][dual="true"] {{
        background-color: {COLOR_SELECTED_BG};
        color: {COLOR_MENU_PRESSED_FG};
        border: 2px solid {COLOR_BORDER_SELECTED};
    }}
    QPushButton[class="menu-button"][pressed="true"][dual="true"]:hover {{
        background-color: #e0eefb;
    }}
"""

RESULTS_LIST_STYLE = f"""
    QListWidget::item {{
        border-left: 3px solid transparent;
    }}
    QListWidget::item:hover {{
        border-left: 3px solid {COLOR_BORDER_DEFAULT};
        background: {COLOR_HOVER_BG};
        color: black;
    }}
    QListWidget::item:selected {{
        border-left: 3px solid {COLOR_BORDER_SELECTED};
        background: {COLOR_SELECTED_BG};
        color: black;
    }}
    QListWidget::item:selected:!active {{
        border-left: 3px solid {COLOR_BORDER_SELECTED};
        background: {COLOR_SELECTED_BG};
        color: black;
    }}
"""

ENTRY_STYLESHEET = f"""
    body {{
        font-family: {FONT_STACK};
        font-size: 12pt;
        line-height: 1.4;
        margin: 0;
        text-align: justify;
    }}
    .hw {{ font-weight: bold; font-style: normal; }}
    .g, .ex, .i {{ font-style: italic; }}
    .st {{ font-style: italic; }}
    .t {{ font-style: normal; }}

    .b, .n {{ font-weight: bold; }}
    .abbr {{ font-weight: bold; }}
    .see {{ font-style: italic; }}
    .p {{ font-style: normal; font-weight: normal; }}
    .h1 {{ font-weight: bold; font-size: 16pt; }}
    .h2 {{ font-weight: bold; font-size: 14pt; }}
    h1, h2 {{ margin: 0; }}

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
    h1 {{ font-weight: bold; font-size: 16pt; }}
    h2 {{ font-weight: bold; font-size: 14pt; }}
    .preview-hw {{
        border-left: 3px solid transparent;
        padding: 2px 0 2px 5px;
        margin-top: 4px;
        font-weight: bold;
    }}
    .preview-no-results {{
        border-left: 3px solid transparent;
        padding: 2px 0 2px 5px;
    }}
    a.preview-hw-link {{
        color: black;
        text-decoration: none;
    }}
    a.preview-hw-link:hover {{
        color: black;
        text-decoration: none;
        border-left: 3px solid {COLOR_BORDER_DEFAULT};
        background: {COLOR_HOVER_BG};
    }}
"""
