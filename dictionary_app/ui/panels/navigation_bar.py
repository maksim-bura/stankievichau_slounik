from PySide6.QtWidgets import QWidget, QVBoxLayout
from ..buttons import NavigationBar


class NavigationBarPanel:
    def __init__(self, parent_window):
        self.parent = parent_window
        self.widget = QWidget()
        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        
        self.navigation_bar = NavigationBar(parent_window)
        self.navigation_bar.hide()
        self.layout.addWidget(self.navigation_bar)
        
        self.widget.setLayout(self.layout)
    
    def get_widget(self):
        return self.widget
    
    def get_bar(self):
        return self.navigation_bar
    
    def push_entry(self, headword, sense_parts, old_headword):
        self.navigation_bar.push_entry(headword, sense_parts, old_headword)
        self.navigation_bar.raise_()
    
    def clear_stack(self):
        self.navigation_bar.clear_stack()
    
    def navigate_to(self, headword, sense_parts):
        self.parent.open_entry_by_headword(headword, sense_parts, from_navigation=True)