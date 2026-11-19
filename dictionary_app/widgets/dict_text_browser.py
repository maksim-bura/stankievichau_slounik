from PySide6.QtWidgets import QStyle, QStyleOptionFrame, QProxyStyle, QTextBrowser, QTextEdit
from PySide6.QtGui import QTextDocument
from dictionary_app.theme.layout_constants import DOCUMENT_MARGIN
from dictionary_app.theme.styles import ENTRY_STYLESHEET
from dictionary_app.utils.constants import SCHEME_WORD, SCHEME_SOURCE, SCHEME_PREVIEW


class NoBlueFocusFrameStyle(QProxyStyle):
    def styleHint(self, hint, option=None, widget=None, returnData=None):
        if hint == QStyle.StyleHint.SH_TextControl_FocusIndicatorTextCharFormat:
            return 0
        return super().styleHint(hint, option, widget, returnData)

    def drawPrimitive(self, element, option, painter, widget=None):
        if element == QStyle.PrimitiveElement.PE_Frame and isinstance(widget, QTextEdit):
            opt = QStyleOptionFrame(option)
            opt.state &= ~QStyle.StateFlag.State_HasFocus
            return super().drawPrimitive(element, opt, painter, widget)
        return super().drawPrimitive(element, option, painter, widget)


def install_no_blue_focus_style(widget):
    style = NoBlueFocusFrameStyle()
    style.setParent(widget)
    widget.setStyle(style)


class DictTextBrowser(QTextBrowser):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setOpenLinks(False)
        install_no_blue_focus_style(self)
        self._document = None

    def setSource(self, url):
        if url.scheme() in (SCHEME_WORD, SCHEME_SOURCE, SCHEME_PREVIEW):
            return
        super().setSource(url)

    def setHtml(self, html):
        document = QTextDocument()
        document.setDefaultStyleSheet(ENTRY_STYLESHEET)
        document.setHtml(html)
        frame_format = document.rootFrame().frameFormat()
        frame_format.setLeftMargin(DOCUMENT_MARGIN)
        frame_format.setRightMargin(DOCUMENT_MARGIN)
        document.rootFrame().setFrameFormat(frame_format)
        previous = self._document
        self.setDocument(document)
        self._document = document
        if previous is not None:
            previous.deleteLater()
