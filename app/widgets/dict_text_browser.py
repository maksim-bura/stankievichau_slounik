from PySide6.QtWidgets import QTextBrowser
from theme.layout_constants import DOCUMENT_MARGIN


class DictTextBrowser(QTextBrowser):
    def setSource(self, url):
        if url.scheme() in ('word', 'source'):
            return
        super().setSource(url)

    def setHtml(self, html):
        super().setHtml(html)
        doc = self.document()
        fmt = doc.rootFrame().frameFormat()
        fmt.setLeftMargin(DOCUMENT_MARGIN)
        fmt.setRightMargin(DOCUMENT_MARGIN)
        doc.rootFrame().setFrameFormat(fmt)
