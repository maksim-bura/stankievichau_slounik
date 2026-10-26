from PySide6.QtWidgets import QStyle, QStyleOptionFrame, QProxyStyle, QTextBrowser, QTextEdit
from dictionary_app.theme.layout_constants import DOCUMENT_MARGIN
from dictionary_app.theme.styles import ENTRY_STYLESHEET
from dictionary_app.utils.constants import SCHEME_WORD, SCHEME_SOURCE, SCHEME_PREVIEW


class NoBlueFocusFrameStyle(QProxyStyle):
    def drawPrimitive(self, element, option, painter, widget=None):
        if element == QStyle.PrimitiveElement.PE_Frame and isinstance(widget, QTextEdit):
            opt = QStyleOptionFrame(option)
            opt.state &= ~QStyle.StateFlag.State_HasFocus
            return super().drawPrimitive(element, opt, painter, widget)
        return super().drawPrimitive(element, option, painter, widget)


class DictTextBrowser(QTextBrowser):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setOpenLinks(False)
        self.setStyle(NoBlueFocusFrameStyle(self.style()))
        self.document().setDefaultStyleSheet(ENTRY_STYLESHEET)

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