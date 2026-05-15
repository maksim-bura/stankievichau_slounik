from .constants import FONT_FAMILY, FONT_SIZE

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

TOOLTIP_STYLE = """
    QToolTip {
        font-family: 'Cambria', 'Times New Roman', Times, serif;
        font-size: 12pt;
        background-color: #ffffcc;
        color: black;
        border: 1px solid #c0c0c0;
    }
"""

SOURCES_BUTTON_STYLE = """
    QPushButton[class="sources-button"] {
        background-color: #f0f0f0;
        color: black;
        font-weight: bold;
        border: 2px solid #c0c0c0;
        border-radius: 5px;
        padding: 5px;
        font-family: 'Cambria', 'Times New Roman', Times, serif;
        font-size: 12pt;
    }
    QPushButton[class="sources-button"]:hover {
        background-color: #e0e0e0;
    }
    QPushButton[class="sources-button"][pressed="true"] {
        background-color: #deeef9;
        color: #1e3a5f;
        border: 2px solid #7c9ec0;
    }
    QPushButton[class="sources-button"][pressed="true"]:hover {
        background-color: #cde2f4;
    }
"""