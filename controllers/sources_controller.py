import os
import re
import xml.etree.ElementTree as ElementTree
import utils.xml_formatter as formatter


class SourcesController:
    def __init__(self):
        self.original_content = None
        self.content = None
        self.current_anchor = None
        self.load_content()

    def load_content(self):
        sources_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'data', 'sources.xml'
        )
        tree = ElementTree.parse(sources_path)
        entry = tree.getroot().find('entry')
        if entry is not None:
            self.original_content = formatter.format_entry(
                ElementTree.tostring(entry, encoding='unicode'),
                is_sources=True
            )
            self.content = self.original_content
        else:
            self.content = "<body>No sources found</body>"
            self.original_content = self.content

    def get_content(self):
        return self.content

    def get_original_content(self):
        return self.original_content

    def get_current_anchor(self):
        return self.current_anchor

    def prepare_scroll(self, source_abbreviation):
        anchor = source_abbreviation.rstrip(':').rstrip('.')
        marker = '➡️'

        if self.current_anchor:
            old_pattern = f'(<span id="{self.current_anchor}"[^>]*>)➡️'
            self.content = re.sub(old_pattern, r'\1', self.content)

        search_pattern = f'id="{anchor}"'
        if search_pattern in self.content:
            pattern = f'(<span id="{anchor}"[^>]*>)'
            self.content = re.sub(pattern, f'\\1{marker}', self.content, count=1)
            self.current_anchor = anchor

        return anchor

    def reset_content(self):
        self.content = self.original_content
        self.current_anchor = None