from PySide6.QtGui import QColor, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import QTextEdit


def background_selections(edit, spans, color):
    fmt = QTextCharFormat()
    fmt.setBackground(QColor(color))
    return _selections(edit, spans, fmt)


def underline_selections(edit, spans, color):
    fmt = QTextCharFormat()
    fmt.setFontUnderline(True)
    fmt.setUnderlineColor(QColor(color))
    return _selections(edit, spans, fmt)


def _selections(edit, spans, fmt):
    selections = []
    for start, end in spans:
        selection = QTextEdit.ExtraSelection()
        selection.format = fmt
        selection.cursor = edit.textCursor()
        selection.cursor.setPosition(start)
        selection.cursor.setPosition(end, QTextCursor.KeepAnchor)
        selections.append(selection)
    return selections
