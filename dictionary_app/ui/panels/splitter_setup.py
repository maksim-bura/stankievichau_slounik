from PySide6.QtWidgets import QSplitter, QSizePolicy
from PySide6.QtCore import Qt


class SplitterSetup:
    @staticmethod
    def create(parent_window, results_list, entry_container, sources_viewer, entry_min_width, sources_min_width):
        bottom_splitter = QSplitter(Qt.Horizontal)
        
        bottom_splitter.addWidget(results_list)
        
        entry_container.setMinimumWidth(entry_min_width)
        entry_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        bottom_splitter.addWidget(entry_container)
        
        sources_viewer.setMinimumWidth(sources_min_width)
        sources_viewer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        bottom_splitter.addWidget(sources_viewer)
        
        bottom_splitter.setCollapsible(1, False)
        bottom_splitter.setCollapsible(2, False)
        
        bottom_splitter.setSizes([200, 400, 400])
        
        return bottom_splitter