import os
import re

from dictionary_app.db.build_database import get_source_path
from dictionary_app.utils.normalize_headword import resolve_headword
from markup_app.services.entry_blocks import (
    block_headwords, block_link, block_matches, find_entry_blocks
)
from markup_app.services.link_text import normalize_headword


class SourceBlocks:
    def __init__(self, search_engine):
        self._search_engine = search_engine
        self._cache = {}

    def clear(self):
        self._cache.clear()

    def invalidate(self, source_file):
        self._cache.pop(source_file, None)

    def load(self, source_file):
        cached = self._cache.get(source_file)
        if cached is not None:
            return cached
        file_path = get_source_path(source_file)
        if not os.path.exists(file_path):
            return None
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except OSError:
            return None
        blocks = find_entry_blocks(content)
        by_link = {}
        by_headword = {}
        for i, block in enumerate(blocks):
            link_norm = block_link(block)
            if link_norm is not None:
                by_link.setdefault(link_norm, []).append(i)
            for hw_norm in block_headwords(block):
                by_headword.setdefault(hw_norm, []).append(i)
        loaded = {
            'content': content,
            'blocks': blocks,
            'by_link': by_link,
            'by_headword': by_headword,
        }
        self._cache[source_file] = loaded
        return loaded

    def iter_blocks(self):
        cursor = self._search_engine._get_connection().cursor()
        cursor.execute("SELECT DISTINCT source_file FROM dictionary")
        source_files = [r[0] for r in cursor.fetchall() if r[0]]
        for source_file in source_files:
            loaded = self.load(source_file)
            if loaded is None:
                continue
            for block in loaded['blocks']:
                yield source_file, block

    def entry_block_candidates(self, source_file, headword, entry_link, keep_acc=0):
        if not source_file:
            return []
        loaded = self.load(source_file)
        if loaded is None:
            return []
        blocks = loaded['blocks']
        t_norm = resolve_headword(headword, keep_acc) if headword else None
        link_norm = normalize_headword(entry_link) if entry_link else None

        if link_norm:
            candidates = []
            for i in loaded['by_link'].get(link_norm, ()):
                block = blocks[i]
                if t_norm is None or block_matches(block, t_norm):
                    candidates.append(block)
            if candidates:
                return candidates

        if t_norm:
            return [blocks[i] for i in loaded['by_headword'].get(t_norm, ())]
        return []

    def entry_block(self, entry_id, source_file, headword, entry_link, keep_acc=0):
        candidates = self.entry_block_candidates(
            source_file, headword, entry_link, keep_acc)
        if not candidates:
            return None
        if len(candidates) == 1:
            return candidates[0]
        full = self._search_engine.get_full_entry(entry_id)
        if full is not None:
            target = re.sub(r'\s+', '', full)
            for block in candidates:
                if re.sub(r'\s+', '', block) == target:
                    return block
        return candidates[0]

    def strict_entry_block(self, entry_id, source_file, headword, entry_link,
                           keep_acc=0):
        candidates = self.entry_block_candidates(
            source_file, headword, entry_link, keep_acc)
        if len(candidates) == 1:
            return candidates[0]
        full = self._search_engine.get_full_entry(entry_id)
        if full is not None:
            target = re.sub(r'\s+', '', full)
            matches = [
                block for block in candidates
                if re.sub(r'\s+', '', block) == target
            ]
            if len(matches) == 1:
                return matches[0]
        return None
