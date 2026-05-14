from PySide6.QtGui import QTextCursor, QTextCharFormat, QColor
from PySide6.QtWidgets import QTextEdit


class SourcesSearchHighlighter:
    def __init__(self, text_browser):
        self.viewer = text_browser

    def highlight(self, text):
        extra_selections = []
        if text:
            cursor = self.viewer.textCursor()
            cursor.movePosition(QTextCursor.Start)
            self.viewer.setTextCursor(cursor)
            fmt = QTextCharFormat()
            fmt.setBackground(QColor(255, 255, 0))
            while self.viewer.find(text):
                sel = self.viewer.extraSelections()[0] if self.viewer.extraSelections() else None
                if sel:
                    sel.cursor = self.viewer.textCursor()
                    sel.format = fmt
                    extra_selections.append(sel)
        self.viewer.setExtraSelections(extra_selections)

    def clear(self):
        self.viewer.setExtraSelections([])