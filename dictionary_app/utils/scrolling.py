from PySide6.QtWidgets import QTextBrowser


class ScrollManager:
    def __init__(self, text_browser):
        self.viewer = text_browser
        self.last_anchor = None
        self.cached_html = None
        self.cached_scroll = 0

    def scroll_to_anchor(self, anchor_id):
        self.viewer.scrollToAnchor(anchor_id)
        self.last_anchor = anchor_id

    def handle_resize(self):
        if self.last_anchor:
            self.scroll_to_anchor(self.last_anchor)

    def cache_state(self):
        self.cached_html = self.viewer.toHtml()
        self.cached_scroll = self.viewer.verticalScrollBar().value()

    def restore_state(self):
        if self.cached_html:
            self.viewer.setHtml(self.cached_html)
            self.viewer.verticalScrollBar().setValue(self.cached_scroll)

    def clear_cache(self):
        self.cached_html = None
        self.cached_scroll = 0
        self.last_anchor = None