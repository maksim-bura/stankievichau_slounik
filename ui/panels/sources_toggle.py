class SourcesToggle:
    def __init__(self, parent_window):
        self.parent = parent_window

    def _handle_showing(self, sizes, results_width, entry_min_width, sources_min_width, entry_current_width, bottom_splitter):
        total_content_width = self.parent.width() - results_width
        required_width = entry_min_width + sources_min_width

        if total_content_width >= required_width:
            half = total_content_width // 2
            bottom_splitter.setSizes([results_width, half, half])
        else:
            half = (self.parent.width() - results_width) // 2
            bottom_splitter.setSizes([results_width, half, half])
            new_width = self.parent.width() + half
            self.parent.resize(new_width, self.parent.height())

    def _handle_hiding(self, sizes, results_width, sources_current_width, bottom_splitter):
        bottom_splitter.setSizes([results_width, results_width + sources_current_width, 0])

    def _handle_already_visible(self, sizes, results_width, bottom_splitter):
        if sizes[2] == 0:
            total_content_width = self.parent.width() - results_width
            half = total_content_width // 2
            bottom_splitter.setSizes([results_width, half, half])

    def _handle_already_hidden(self, sizes, results_width, bottom_splitter):
        bottom_splitter.setSizes([results_width, results_width + sizes[2], 0])

    def toggle(self, sources_visible, sources, sources_button, bottom_splitter, entry_min_width, sources_min_width, entry_scroll_manager):
        entry_scroll_manager.cache_state()

        was_visible = sources_visible
        sources_visible = sources.toggle()
        sources_button.set_sources_visible(sources_visible)

        sizes = bottom_splitter.sizes()
        results_width = sizes[0]
        entry_current_width = sizes[1]
        sources_current_width = sizes[2]

        if sources_visible and not was_visible:
            self._handle_showing(sizes, results_width, entry_min_width, sources_min_width, entry_current_width, bottom_splitter)
        elif not sources_visible and was_visible:
            self._handle_hiding(sizes, results_width, sources_current_width, bottom_splitter)
        else:
            if sources_visible:
                self._handle_already_visible(sizes, results_width, bottom_splitter)
            else:
                self._handle_already_hidden(sizes, results_width, bottom_splitter)

        entry_scroll_manager.restore_state()
        return sources_visible