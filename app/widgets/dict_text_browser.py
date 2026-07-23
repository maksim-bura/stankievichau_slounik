from PySide6.QtWidgets import QTextBrowser
from PySide6.QtGui import QGuiApplication
from theme.layout_constants import DOCUMENT_MARGIN


class DictTextBrowser(QTextBrowser):
    _last_selected_text = ""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.selectionChanged.connect(self._on_selection_changed)

    def _on_selection_changed(self):
        cursor = self.textCursor()
        if cursor.hasSelection():
            DictTextBrowser._last_selected_text = cursor.selectedText()
        else:
            DictTextBrowser._last_selected_text = ""

    def setSource(self, url):
        if url.scheme() in ('word', 'source', 'preview'):
            return
        super().setSource(url)

    def setHtml(self, html):
        super().setHtml(html)
        doc = self.document()
        fmt = doc.rootFrame().frameFormat()
        fmt.setLeftMargin(DOCUMENT_MARGIN)
        fmt.setRightMargin(DOCUMENT_MARGIN)
        doc.rootFrame().setFrameFormat(fmt)