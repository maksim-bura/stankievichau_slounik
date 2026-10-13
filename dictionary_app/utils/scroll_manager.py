class ScrollManager:
    def __init__(self, viewer):
        self.viewer = viewer
        self.last_anchor = None
        self.cached_scroll = 0

    def scroll_to_anchor(self, anchor_id):
        self.viewer.scrollToAnchor(anchor_id)
        self.last_anchor = anchor_id

    def handle_resize(self):
        if self.last_anchor:
            self.scroll_to_anchor(self.last_anchor)

    def cache_scroll(self):
        self.cached_scroll = self.viewer.verticalScrollBar().value()

    def restore_content(self, html):
        self.viewer.setHtml(html)
        self.viewer.verticalScrollBar().setValue(self.cached_scroll)

    def clear_cache(self):
        self.cached_scroll = 0
        self.last_anchor = None
