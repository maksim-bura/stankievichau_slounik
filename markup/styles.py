MARKUP_GLOBAL_STYLE = """
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
    QTabWidget::pane {
        border-top: 1px solid #c0c0c0;
    }
    QTabBar::tab {
        padding: 4px 12px;
        margin-right: 2px;
    }
    QTabBar::tab:selected {
        background-color: #edf7fd;
        border-bottom: 2px solid #7c9ec0;
    }
"""

ENTRY_LIST_STYLE = """
    QListWidget::item {
        border-left: 3px solid transparent;
        padding: 1px;
    }
"""

CHECKED_TOGGLE_STYLE = """
    QPushButton {
        border: none;
        background-color: transparent;
        color: black;
        padding: 0px;
    }
    QPushButton:hover {
        color: #7c9ec0;
    }
"""

TAG_BUTTON_STYLE = """
    QPushButton {
        border: none;
        background-color: transparent;
        color: black;
        padding: 2px 6px;
    }
    QPushButton:hover {
        color: #7c9ec0;
    }
"""
