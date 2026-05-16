from PySide6.QtWidgets import QTextBrowser


class DictTextBrowser(QTextBrowser):
    def setSource(self, url):
        if url.scheme() in ('word', 'source'):
            return
        super().setSource(url)
