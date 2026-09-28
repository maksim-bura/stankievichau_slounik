from PySide6.QtWidgets import QStyle, QStyleOptionFrame, QProxyStyle, QTextBrowser
from theme.layout_constants import DOCUMENT_MARGIN
from utils.constants import SCHEME_WORD, SCHEME_SOURCE, SCHEME_PREVIEW


class NoBlueFocusFrameStyle(QProxyStyle):
    def drawPrimitive(self, element, option, painter, widget=None):
        if element == QStyle.PrimitiveElement.PE_Frame and isinstance(widget, QTextBrowser):
            opt = QStyleOptionFrame(option)
            opt.state &= ~QStyle.StateFlag.State_HasFocus
            return super().drawPrimitive(element, opt, painter, widget)
        return super().drawPrimitive(element, option, painter, widget)


class DictTextBrowser(QTextBrowser):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyle(NoBlueFocusFrameStyle(self.style()))

    def setSource(self, url):
        if url.scheme() in (SCHEME_WORD, SCHEME_SOURCE, SCHEME_PREVIEW):
            return
        super().setSource(url)

    def setHtml(self, html):
        super().setHtml(html)
        doc = self.document()
        fmt = doc.rootFrame().frameFormat()
        fmt.setLeftMargin(DOCUMENT_MARGIN)
        fmt.setRightMargin(DOCUMENT_MARGIN)
        doc.rootFrame().setFrameFormat(fmt)