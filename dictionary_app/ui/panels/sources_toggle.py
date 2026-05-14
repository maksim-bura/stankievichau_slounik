from PySide6.QtWidgets import QApplication


class SourcesToggle:
    def __init__(self, parent_window):
        self.parent = parent_window
    
    def toggle(self, sources_visible, sources, sources_button, bottom_splitter, entry_min_width, sources_min_width, restore_cached_entry_state, entry_scroll_manager):
        entry_scroll_manager.cache_state()
        
        was_visible = sources_visible
        sources_visible = sources.toggle()
        sources_button.set_sources_visible(sources_visible)
        
        sizes = bottom_splitter.sizes()
        results_width = sizes[0]
        entry_current_width = sizes[1]
        sources_current_width = sizes[2]
        
        if sources_visible and not was_visible:
            total_content_width = self.parent.width() - results_width
            required_width = entry_min_width + sources_min_width
            
            if total_content_width >= required_width:
                half = total_content_width // 2
                bottom_splitter.setSizes([results_width, half, half])
            else:
                new_width = self.parent.width() + sources_min_width
                self.parent.resize(new_width, self.parent.height())
                bottom_splitter.setSizes([results_width, entry_current_width, sources_min_width])
        
        elif not sources_visible and was_visible:
            bottom_splitter.setSizes([results_width, results_width + sources_current_width, 0])
        
        else:
            if sources_visible:
                if sizes[2] == 0:
                    total_content_width = self.parent.width() - results_width
                    half = total_content_width // 2
                    bottom_splitter.setSizes([results_width, half, half])
            else:
                bottom_splitter.setSizes([results_width, results_width + sizes[2], 0])
        
        restore_cached_entry_state()
        return sources_visible