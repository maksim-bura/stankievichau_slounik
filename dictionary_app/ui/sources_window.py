from PySide6.QtWidgets import QTextBrowser, QApplication, QVBoxLayout, QWidget, QPushButton, QGridLayout, QLineEdit, QHBoxLayout
from PySide6.QtCore import Qt
import os
import re
import xml.etree.ElementTree as ElementTree
import utils.xml_formatter as formatter
from utils.scrolling import ScrollManager
from localization import strings


class SourcesWindow:
    def __init__(self, parent_window):
        self.parent = parent_window
        self.sources_visible = False
        self.original_content = None
        self.original_raw_xml = None
        self.content = None
        self.current_anchor = None
        self.search_visible = False

        self.container = QWidget()
        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        self.search_container = QWidget()
        self.search_container.setAutoFillBackground(False)
        search_layout = QHBoxLayout()
        search_layout.setContentsMargins(5, 0, 5, 0)
        search_layout.setSpacing(5)

        self.search_line = QLineEdit()
        self.search_line.setPlaceholderText(strings.sources_search_placeholder)
        self.search_line.setClearButtonEnabled(False)
        self.search_line.setFixedHeight(30)
        self.search_line.setVisible(False)
        self.search_line.setStyleSheet("""
            QLineEdit {
                background-color: white;
                border: 1px solid #c0c0c0;
                border-radius: 3px;
                padding: 2px;
            }
            QLineEdit:focus {
                background-color: white;
            }
        """)
        search_layout.addWidget(self.search_line, 1)

        self.close_search_button = QPushButton("❌")
        self.close_search_button.setCursor(Qt.PointingHandCursor)
        self.close_search_button.setFlat(True)
        self.close_search_button.setFixedSize(30, 30)
        self.close_search_button.setStyleSheet("background-color: transparent; border: none;")
        self.close_search_button.setVisible(False)
        self.close_search_button.clicked.connect(self.close_search_bar)

        search_layout.addWidget(self.close_search_button)

        self.search_container.setLayout(search_layout)
        self.layout.addWidget(self.search_container)

        self.floating_button = QPushButton("🔍")
        self.floating_button.setCursor(Qt.PointingHandCursor)
        self.floating_button.setFlat(True)
        self.floating_button.setFixedSize(30, 30)
        self.floating_button.setStyleSheet("background-color: transparent; border: none;")
        self.floating_button.clicked.connect(self.open_search_bar)

        self.viewer_wrapper = QWidget()
        self.viewer_wrapper.setAutoFillBackground(False)
        wrapper_layout = QGridLayout()
        wrapper_layout.setContentsMargins(0, 0, 0, 0)
        wrapper_layout.setSpacing(0)

        self.viewer = QTextBrowser()
        self.viewer.setReadOnly(True)
        self.viewer.setOpenExternalLinks(False)
        self.viewer.anchorClicked.connect(parent_window.on_link_clicked)
        self.viewer.setFocusPolicy(Qt.NoFocus)
        wrapper_layout.addWidget(self.viewer, 0, 0)

        wrapper_layout.addWidget(self.floating_button, 0, 0, alignment=Qt.AlignTop | Qt.AlignRight)

        self.viewer_wrapper.setLayout(wrapper_layout)
        self.layout.addWidget(self.viewer_wrapper)

        self.container.setLayout(self.layout)
        self.container.hide()

        self.scroll_manager = ScrollManager(self.viewer)
        self.load_content()

    def open_search_bar(self):
        self.search_visible = True
        self.search_line.setVisible(True)
        self.close_search_button.setVisible(True)
        self.floating_button.setVisible(False)
        self.search_line.setFocus()

    def close_search_bar(self):
        self.search_visible = False
        self.search_line.clear()
        self.search_line.setVisible(False)
        self.close_search_button.setVisible(False)
        self.floating_button.setVisible(True)

    def load_content(self):
        sources_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'data', 'sources.xml'
        )
        try:
            tree = ElementTree.parse(sources_path)
            entry = tree.getroot().find('entry')
            if entry is not None:
                self.original_content = formatter.format_entry(ElementTree.tostring(entry, encoding='unicode'), is_sources=True)
                self.content = self.original_content
            else:
                self.content = "<body>No sources found</body>"
                self.original_content = self.content
        except Exception:
            self.content = "<body>Error loading sources</body>"
            self.original_content = self.content

    def scroll_to_source(self, source_abbreviation):
        if self.search_visible:
            self.close_search_bar()
        else:
            self.search_line.clear()

        if not self.original_content:
            return

        anchor = source_abbreviation.rstrip(':').rstrip('.')
        marker = '➡️'

        if not self.sources_visible:
            self.content = self.original_content
            search_pattern = f'id="{anchor}"'
            if search_pattern in self.content:
                pattern = f'(<span id="{anchor}"[^>]*>)'
                self.content = re.sub(pattern, f'\\1{marker}', self.content, count=1)
                self.current_anchor = anchor
            self.viewer.setHtml(self.content)
            self.container.show()
            self.sources_visible = True
            QApplication.processEvents()
            self.scroll_manager.scroll_to_anchor(anchor)
        else:
            if self.current_anchor:
                old_pattern = f'(<span id="{self.current_anchor}"[^>]*>)➡️'
                self.content = re.sub(old_pattern, r'\1', self.content)
            search_pattern = f'id="{anchor}"'
            if search_pattern in self.content:
                pattern = f'(<span id="{anchor}"[^>]*>)'
                self.content = re.sub(pattern, f'\\1{marker}', self.content, count=1)
                self.current_anchor = anchor
            old_focus = self.parent.entry_viewer.hasFocus()
            current_scroll = self.viewer.verticalScrollBar().value()
            self.viewer.setHtml(self.content)
            self.viewer.verticalScrollBar().setValue(current_scroll)
            if old_focus:
                self.parent.entry_viewer.setFocus()
            QApplication.processEvents()
            self.scroll_manager.scroll_to_anchor(anchor)

    def toggle(self):
        self.sources_visible = not self.sources_visible
        if self.sources_visible:
            if self.content:
                self.viewer.setHtml(self.content)
                QApplication.processEvents()
                if self.current_anchor:
                    self.scroll_manager.scroll_to_anchor(self.current_anchor)
            self.container.show()
        else:
            self.container.hide()
            self.content = self.original_content
            self.current_anchor = None
            self.scroll_manager.last_anchor = None
            if self.search_visible:
                self.close_search_bar()
        return self.sources_visible

    def handle_resize(self):
        self.scroll_manager.handle_resize()

    def get_viewer(self):
        return self.container