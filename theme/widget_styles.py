GLOBAL_STYLE = """
    QWidget {
        font-family: 'Cambria', 'Times New Roman', Times, serif;
        font-size: 12pt;
    }
    QListWidget {
        font-family: 'Cambria', 'Times New Roman', Times, serif;
        font-size: 12pt;
        font-weight: bold;
    }
    QLineEdit {
        font-family: 'Cambria', 'Times New Roman', Times, serif;
        font-size: 12pt;
        background-color: white;
        border: 1px solid #c0c0c0;
        border-radius: 3px;
        padding: 2px;
    }
    QLineEdit:focus {
        background-color: white;
    }
    QToolTip {
        font-family: 'Cambria', 'Times New Roman', Times, serif;
        font-size: 12pt;
        background-color: #ffffcc;
        color: black;
        border: 1px solid #c0c0c0;
    }
"""

FLAT_BUTTON_STYLE = """
    QPushButton {
        border: none;
        background-color: transparent;
        color: black;
        padding: 0px;
    }
"""

SEARCH_BOX_STYLE = """
    QLineEdit {
        background-color: white;
        border: 1px solid #c0c0c0;
        border-radius: 3px;
        padding: 2px;
    }
    QLineEdit:focus {
        background-color: white;
    }
"""

MENU_BUTTON_STYLE = """
    QPushButton[class="menu-button"] {
        background-color: #fafafa;
        color: black;
        font-weight: bold;
        border: 2px solid #c0c0c0;
        border-radius: 5px;
        padding: 5px;
        font-family: 'Cambria', 'Times New Roman', Times, serif;
        font-size: 12pt;
    }
    QPushButton[class="menu-button"]:hover {
        background-color: #ececec;
    }
    QPushButton[class="menu-button"][pressed="true"] {
        background-color: #edf7fd;
        color: #1e3a5f;
        border: 2px solid #7c9ec0;
    }
    QPushButton[class="menu-button"][pressed="true"]:hover {
        background-color: #e0eefb;
    }
    QPushButton[class="menu-button"][pressed="true"][dual="true"] {
        background-color: #edf7fd;
        color: #1e3a5f;
        border: 2px solid #7c9ec0;
    }
    QPushButton[class="menu-button"][pressed="true"][dual="true"]:hover {
        background-color: #e0eefb;
    }
"""

ENTRY_STYLESHEET = """
    body {
        font-family: 'Cambria', 'Times New Roman', Times, serif;
        font-size: 12pt;
        line-height: 1.4;
        margin: 0;
        text-align: justify;
    }
    .hw { font-weight: bold; }
    .g, .ex, .i { font-style: italic; }
    .t { font-style: normal; }
    .b { font-weight: bold; }
    .abbr { font-weight: bold; }
    .see { font-style: italic; }
    .p { font-style: normal; font-weight: normal; }
    .h1 { font-weight: bold; font-size: 16pt; }
    .h2 { font-weight: bold; font-size: 14pt; }
    h1, h2 { margin: 0; }

    .sense { font-style: normal; }
    .headword-arrow { font-weight: normal; margin-right: 4px; }
    .sense-arrow { font-weight: normal; margin-right: 4px; }
    .link, .word-link {
        font-style: italic; color: inherit;
        text-decoration: none; cursor: pointer;
    }
    .link:visited, .word-link:visited, .source-link:visited {
        text-decoration: none; color: inherit;
    }
    .link:hover, .word-link:hover { text-decoration: underline; }
    .src, .source-link { font-style: normal; }
    .source-link { font-style: normal; color: inherit; text-decoration: none; cursor: pointer; }
    .source-link:hover { text-decoration: underline; }
    .search-highlight { background-color: #FFF9C4; }
    a, a:visited { text-decoration: none; color: inherit; }
    a:hover { text-decoration: underline; }
    .toggle-btn, .toggle-btn:visited, .toggle-btn:hover {
        text-decoration: none; color: inherit; cursor: pointer;
    }
    h1 { font-weight: bold; font-size: 16pt; }
    h2 { font-weight: bold; font-size: 14pt; }
    .preview-hw {
        border-left: 3px solid transparent;
        padding: 2px 0 2px 5px;
        margin-top: 4px;
        font-weight: bold;
    }
    .preview-no-results {
        border-left: 3px solid transparent;
        padding: 2px 0 2px 5px;
    }
    a.preview-hw-link {
        color: black;
        text-decoration: none;
    }
    a.preview-hw-link:hover {
        color: black;
        text-decoration: none;
        border-left: 3px solid #c0c0c0;
        background: #fafafa;
    }
"""
