from PySide6.QtWidgets import QPushButton, QSizePolicy, QHBoxLayout, QWidget, QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from localization import strings


class SourcesButton(QPushButton):
    def __init__(self, parent=None):
        super().__init__("📚", parent)
        self.sources_visible = False
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.setFixedSize(30, 30)
        self.setCursor(Qt.PointingHandCursor)
        self.setProperty("class", "sources-button")
        self.setToolTip(strings.sources_button)
        self.setStyleSheet("""
            QToolTip {
                font-family: 'Cambria', 'Times New Roman', Times, serif;
                font-size: 12pt;
                background-color: #ffffcc;
                color: black;
                border: 1px solid #c0c0c0;
            }
        """)
        self.update_style()

    def update_style(self):
        if self.sources_visible:
            self.setProperty("pressed", "true")
        else:
            self.setProperty("pressed", "false")
        self.style().unpolish(self)
        self.style().polish(self)

    def toggle(self):
        self.sources_visible = not self.sources_visible
        self.update_style()
        return self.sources_visible

    def set_sources_visible(self, visible):
        self.sources_visible = visible
        self.update_style()


class NavigationBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setVisible(False)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setFixedHeight(30)
        self.setMinimumWidth(250)
        self.setAutoFillBackground(True)
        
        palette = self.palette()
        palette.setColor(self.backgroundRole(), QColor(240, 240, 240))
        self.setPalette(palette)
        self.setAutoFillBackground(True)
        
        layout = QHBoxLayout()
        layout.setContentsMargins(5, 0, 5, 0)
        layout.setSpacing(0)
        
        button_style = """
            QPushButton {
                border: none;
                background-color: transparent;
                color: black;
                padding: 0px;
            }
        """
        
        self.back_button = QPushButton(f"⬅️ {strings.back_button}")
        self.back_button.setCursor(Qt.PointingHandCursor)
        self.back_button.setFlat(True)
        self.back_button.setStyleSheet(button_style)
        self.back_button.setFixedWidth(95)
        self.back_button.clicked.connect(self.on_back)
        
        self.back_spacer = QWidget()
        self.back_spacer.setFixedWidth(95)
        self.back_spacer.setVisible(False)
        
        self.button_spacer = QWidget()
        self.button_spacer.setMinimumWidth(5)
        self.button_spacer.setMaximumWidth(15)
        self.button_spacer.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Fixed)
        
        self.forward_button = QPushButton(f"➡️ {strings.forward_button}")
        self.forward_button.setCursor(Qt.PointingHandCursor)
        self.forward_button.setFlat(True)
        self.forward_button.setStyleSheet(button_style)
        self.forward_button.setFixedWidth(95)
        self.forward_button.clicked.connect(self.on_forward)
        
        self.close_button = QPushButton("❌")
        self.close_button.setCursor(Qt.PointingHandCursor)
        self.close_button.setFlat(True)
        self.close_button.setStyleSheet(button_style)
        self.close_button.setFixedSize(35, 28)
        self.close_button.clicked.connect(self.hide_bar)
        
        layout.addWidget(self.back_button)
        layout.addWidget(self.back_spacer)
        layout.addWidget(self.button_spacer)
        layout.addWidget(self.forward_button)
        layout.addStretch()
        layout.addWidget(self.close_button)
        
        self.setLayout(layout)
        
        self.navigation_stack = []
        self.current_index = -1
        self.parent_window = parent
    
    def update_buttons(self):
        back_visible = self.current_index > 0
        self.back_button.setVisible(back_visible)
        self.back_spacer.setVisible(not back_visible)
        self.forward_button.setVisible(self.current_index < len(self.navigation_stack) - 1)
    
    def on_back(self):
        if self.current_index > 0:
            self.current_index -= 1
            nav_item = self.navigation_stack[self.current_index]
            self.parent_window.navigate_to(nav_item['headword'], nav_item['sense_parts'])
            self.update_buttons()
    
    def on_forward(self):
        if self.current_index < len(self.navigation_stack) - 1:
            self.current_index += 1
            nav_item = self.navigation_stack[self.current_index]
            self.parent_window.navigate_to(nav_item['headword'], nav_item['sense_parts'])
            self.update_buttons()
    
    def hide_bar(self):
        self.setVisible(False)
        self.navigation_stack = []
        self.current_index = -1
        self.update_buttons()
    
    def push_entry(self, headword, sense_parts, old_headword):
        if headword == old_headword:
            return
        
        if self.navigation_stack == [] and old_headword is not None:
            self.navigation_stack.append({
                'headword': old_headword,
                'sense_parts': None
            })
            self.current_index = 0
        
        if self.navigation_stack and self.current_index >= 0 and self.navigation_stack[self.current_index]['headword'] == old_headword:
            if self.current_index < len(self.navigation_stack) - 1:
                self.navigation_stack = self.navigation_stack[:self.current_index + 1]
        else:
            if self.current_index < len(self.navigation_stack) - 1:
                self.navigation_stack = self.navigation_stack[:self.current_index + 1]
        
        self.navigation_stack.append({
            'headword': headword,
            'sense_parts': sense_parts
        })
        self.current_index = len(self.navigation_stack) - 1
        self.setVisible(len(self.navigation_stack) > 1)
        self.update_buttons()
    
    def clear_stack(self):
        self.navigation_stack = []
        self.current_index = -1
        self.setVisible(False)
        self.update_buttons()