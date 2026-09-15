class SourcesToggle:
    def __init__(self, main_window):
        self.main_window = main_window

    def _handle_showing(self, results_width, entry_min_width, sources_min_width, bottom_splitter):
        available = self.main_window.width() - results_width
        needed = entry_min_width + sources_min_width

        if available >= needed:
            half = available // 2
            entry_width = half
            sources_width = available - half
        else:
            entry_width = entry_min_width
            sources_width = sources_min_width
            target = results_width + entry_min_width + sources_min_width
            if self.main_window.width() < target:
                self.main_window.resize(target, self.main_window.height())

        bottom_splitter.setSizes([entry_width, sources_width])

    def _handle_hiding(self, bottom_splitter, entry_before_hide, sources_before_hide):
        new_entry = entry_before_hide + sources_before_hide
        bottom_splitter.setSizes([new_entry, 0])

    def _handle_already_visible(self, results_width, entry_min_width, sources_min_width, bottom_splitter):
        if bottom_splitter.sizes()[1] == 0:
            available = self.main_window.width() - results_width
            needed = entry_min_width + sources_min_width
            if available >= needed:
                half = available // 2
                bottom_splitter.setSizes([half, available - half])

    def _handle_already_hidden(self, results_width, bottom_splitter):
        sizes = bottom_splitter.sizes()
        bottom_splitter.setSizes([results_width + sizes[1], 0])

    def toggle(self, sources_visible, sources, sources_button, results_width, bottom_splitter, entry_min_width, sources_min_width):
        was_visible = sources_visible
        sizes_before = bottom_splitter.sizes() if was_visible else None
        sources_visible = sources.toggle()
        sources_button.set_sources_visible(sources_visible)

        if sources_visible and not was_visible:
            self._handle_showing(results_width, entry_min_width, sources_min_width, bottom_splitter)
        elif not sources_visible and was_visible:
            entry_before_hide = sizes_before[0] if sizes_before else bottom_splitter.sizes()[0]
            sources_before_hide = sizes_before[1] if sizes_before else 0
            self._handle_hiding(bottom_splitter, entry_before_hide, sources_before_hide)
        elif sources_visible:
            self._handle_already_visible(results_width, entry_min_width, sources_min_width, bottom_splitter)
        else:
            self._handle_already_hidden(results_width, bottom_splitter)

        return sources_visible