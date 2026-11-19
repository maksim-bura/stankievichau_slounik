import re
import xml.etree.ElementTree as ElementTree

from dictionary_app.utils.normalize_headword import has_keep_acc, resolve_headword, strip_quotes
from dictionary_app.utils.remove_accents import remove_accents
from dictionary_app.utils.xml_schema import (
    ATTR_HW, ATTR_ID, ATTR_ENTRY, ATTR_EXCL, ATTR_KEEP_ACC
)
from markup_app.services.link_indexes import LinkIndexes, index_values
from markup_app.services.link_text import normalize_headword, row_norm, split_sense_tail, strip_tags
from markup_app.utils.xml_patterns import EXCL_ATTR_RE, HW_ATTRS_TEXT_RE, HW_TEXT_RE


MODE_MISSING = 'missing_links'
MODE_UNRESOLVED = 'unresolved_links'
MODE_AMBIGUOUS_G = 'ambiguous_g'
MODE_UNION = 'union'

OUTCOME_RESOLVED = 'resolved'
OUTCOME_MISSING = 'missing'
OUTCOME_UNRESOLVED = 'unresolved'

_SINGLE_REGION_G = 1
_AMBIGUOUS_G_MIN_HW = 2
_AMBIGUOUS_G_MIN_G = 1

_MODE_OUTCOMES = {
    MODE_MISSING: (OUTCOME_MISSING,),
    MODE_UNRESOLVED: (OUTCOME_UNRESOLVED,),
    MODE_UNION: (OUTCOME_MISSING, OUTCOME_UNRESOLVED),
}

_ALL_BROKEN_MODES = frozenset({MODE_MISSING, MODE_UNRESOLVED, MODE_AMBIGUOUS_G})


def expand_broken_mode(mode):
    if isinstance(mode, str):
        if mode == MODE_UNION:
            return set(_ALL_BROKEN_MODES)
        return {mode}
    return set(mode)

_OUTCOME_FLAGS = {
    OUTCOME_MISSING: MODE_MISSING,
    OUTCOME_UNRESOLVED: MODE_UNRESOLVED,
}

_SEE_RE = re.compile(r'<see\b([^>]*?)>(.*?)</see>', re.DOTALL)
_SEE_ATTR_RE = re.compile(r'(\w+)\s*=\s*"([^"]*)"')
_SENSE_TAIL_RE = re.compile(r'^[,\s]*\d')


class BrokenLinkAnalyzer:
    def __init__(self, connection_provider, source_blocks_provider):
        self._source_blocks = source_blocks_provider
        self._indexes = LinkIndexes(connection_provider, source_blocks_provider)
        self._flags = None
        self._occurrences = None

    def invalidate(self):
        self._flags = None
        self._occurrences = None
        self._indexes.invalidate()

    def flags(self):
        if self._flags is not None:
            return self._flags

        flags = {}
        for source_file, block in self._source_blocks():
            entry_ids = self._indexes.entry_ids(block, source_file)
            if not entry_ids:
                continue
            key_ids = entry_ids if len(entry_ids) == 1 else [None]
            for span_flags, hw_norms in self._span_flags(block):
                if not span_flags:
                    continue
                for hw_norm in hw_norms:
                    for entry_id in key_ids:
                        flags.setdefault(
                            (source_file, entry_id, hw_norm), set()
                        ).update(span_flags)
        self._flags = flags
        return flags

    def spans(self, text, mode):
        if isinstance(mode, str):
            wanted = _MODE_OUTCOMES.get(mode) or ()
        else:
            wanted = set()
            for m in mode:
                wanted.update(_MODE_OUTCOMES.get(m) or ())
        if not wanted:
            return []
        spans = []
        for match in _SEE_RE.finditer(text):
            word, entry_attr, hw_attr = self._see_parts_from_match(text, match)
            outcome, _row = self._classify(word, entry_attr, hw_attr)
            if outcome in wanted:
                spans.append((match.start(), match.end()))
        return spans

    def see_occurrences(self):
        if self._occurrences is None:
            self._occurrences = list(self._iter_see_occurrences())
        return iter(self._occurrences)

    def _iter_see_occurrences(self):
        for source_file, block in self._source_blocks():
            for match in _SEE_RE.finditer(block):
                word, entry_attr, hw_attr = self._see_parts_from_match(block, match)
                outcome, row = self._classify(word, entry_attr, hw_attr)
                yield {
                    'source_file': source_file,
                    'block': block,
                    'start': match.start(),
                    'end': match.end(),
                    'word': word,
                    'entry_attr': entry_attr,
                    'hw_attr': hw_attr,
                    'outcome': outcome,
                    'row': row,
                }

    def owning_hw_texts(self, block, see_start):
        try:
            root = ElementTree.fromstring(block)
        except ElementTree.ParseError:
            return self._owning_hw_texts_regex(block)
        target = None
        for elem, match in zip(
            (e for e in root.iter() if e.tag == 'see'),
            _SEE_RE.finditer(block),
        ):
            if match.start() == see_start:
                target = elem
                break
        if target is None:
            return self._owning_hw_texts_regex(block)
        for bucket in self._collect_regions(root).values():
            if any(see is target for see in bucket['see']):
                return [
                    resolve_headword(
                        ''.join(hw.itertext()).strip(),
                        1 if hw.get(ATTR_KEEP_ACC) is not None else 0,
                    )
                    for hw in bucket['hw']
                    if hw.get(ATTR_EXCL) is None
                ]
        return []

    @staticmethod
    def _owning_hw_texts_regex(block):
        return [
            resolve_headword(
                strip_tags(match.group(2)).strip(),
                1 if has_keep_acc(match.group(1)) else 0,
            )
            for match in HW_ATTRS_TEXT_RE.finditer(block)
            if not EXCL_ATTR_RE.search(match.group(1))
        ]

    def ambiguous_spans(self, text):
        try:
            root = ElementTree.fromstring(text)
        except ElementTree.ParseError:
            return self._ambiguous_spans_regex(text)

        regions = self._collect_regions(root)
        all_hws = [elem for elem in root.iter() if elem.tag == 'hw']
        entry_hw_texts = [''.join(hw.itertext()).strip() for hw in all_hws]
        entry_hw_ids = {hw.get(ATTR_ID) or '' for hw in all_hws}
        element_spans = self._element_spans(root, text)

        g_spans = []
        hw_spans = []
        for region in regions.values():
            flags = self._region_flags(region, entry_hw_texts, entry_hw_ids)
            if MODE_AMBIGUOUS_G not in flags:
                continue
            for elem in region['g']:
                span = element_spans.get(elem)
                if span is not None:
                    g_spans.append(span)
            for elem in region['hw']:
                span = element_spans.get(elem)
                if span is not None:
                    hw_spans.append(span)
        return g_spans, hw_spans

    def _ambiguous_spans_regex(self, text):
        def span_gen(tag):
            spans = []
            for m in re.finditer(rf'<{tag}\b', text):
                end = text.find(f'</{tag}>', m.end())
                if end < 0:
                    end = len(text)
                else:
                    end += len(f'</{tag}>')
                spans.append((m.start(), end))
            return spans

        if (len(re.findall(r'<hw\b', text)) >= _AMBIGUOUS_G_MIN_HW
                and len(re.findall(r'<g\b', text)) >= _AMBIGUOUS_G_MIN_G):
            return span_gen('g'), span_gen('hw')
        return [], []

    def _collect_regions(self, root):
        parent_map = {}
        for parent in root.iter():
            for child in parent:
                parent_map[child] = parent

        def nearest_d(elem):
            node = parent_map.get(elem)
            while node is not None:
                if node.tag == 'd':
                    return node
                node = parent_map.get(node)
            return None

        regions = {}
        for elem in root.iter():
            if elem.tag in ('hw', 'g', 'see'):
                bucket = regions.setdefault(
                    nearest_d(elem), {'hw': [], 'g': [], 'see': []}
                )
                bucket[elem.tag].append(elem)
        return regions

    def _element_spans(self, root, text):
        spans = {}
        for tag in ('hw', 'g'):
            matches = list(re.finditer(rf'<{tag}\b', text))
            idx = 0
            for elem in root.iter():
                if elem.tag != tag:
                    continue
                if idx >= len(matches):
                    break
                start = matches[idx].start()
                end = text.find(f'</{tag}>', start)
                if end < 0:
                    end = len(text)
                else:
                    end += len(f'</{tag}>')
                spans[elem] = (start, end)
                idx += 1
        return spans

    def _see_parts_from_match(self, text, match):
        attrs = dict(_SEE_ATTR_RE.findall(match.group(1)))
        inner = strip_tags(match.group(2)).strip()
        word = strip_quotes(inner) or inner or ''
        if '<n' in match.group(2):
            tail = text[match.end():].split('<', 1)[0]
            if word and _SENSE_TAIL_RE.match(tail):
                word += tail
        entry_attr = strip_quotes(attrs.get(ATTR_ENTRY) or '')
        hw_attr = strip_quotes(attrs.get(ATTR_HW) or '')
        return word, entry_attr, hw_attr

    @staticmethod
    def _see_parts(see):
        word = ''.join(see.itertext()).strip()
        word = strip_quotes(word) or word
        entry_attr = strip_quotes(see.get(ATTR_ENTRY) or '')
        hw_attr = strip_quotes(see.get(ATTR_HW) or '')
        if any(child.tag == 'n' for child in see) and see.tail:
            if word and _SENSE_TAIL_RE.match(see.tail):
                word += see.tail
        return word, entry_attr, hw_attr

    def _classify(self, word, entry_attr, hw_attr):
        word, senses = split_sense_tail(word)
        norm = normalize_headword(word)
        word_rows = self._indexes.by_normalized_headword().get(norm, ())
        if word_rows and remove_accents(word) != word:
            exact = self._indexes.by_exact_headword().get(word)
            if exact:
                word_rows = exact
        rows = self._indexes.rows()

        def handle_attrs():
            if entry_attr:
                entry_ids = self._indexes.entry_attr_ids(entry_attr)
                if not entry_ids:
                    return OUTCOME_MISSING, None
                if len(entry_ids) > 1:
                    return OUTCOME_UNRESOLVED, None
                entry_id = next(iter(entry_ids))
                in_entry = index_values(
                    self._indexes.row_indexes()['by_entry'], entry_id
                )
                if hw_attr:
                    hw_ids = self._indexes.hw_attr_indexes(hw_attr)
                    matched = [
                        rows[i] for i in in_entry if i in hw_ids
                    ]
                else:
                    matched = [
                        rows[i] for i in in_entry
                        if normalize_headword(rows[i][1]) == norm
                    ]
                if len(matched) == 1:
                    return self._finalize_resolved(matched[0], senses)
                if not matched:
                    return OUTCOME_MISSING, None
                return OUTCOME_UNRESOLVED, None
            if hw_attr:
                matched = self._indexes.hw_attr_rows(hw_attr)
                if len(matched) == 1:
                    return self._finalize_resolved(matched[0], senses)
                if not matched:
                    return OUTCOME_MISSING, None
                return OUTCOME_UNRESOLVED, None
            return None, None

        if entry_attr or hw_attr:
            outcome, row = handle_attrs()
            if outcome is not None:
                return outcome, row

        if len(word_rows) == 1:
            return self._finalize_resolved(word_rows[0], senses)

        outcome, row = handle_attrs()
        if not word_rows:
            return (outcome or OUTCOME_MISSING), row
        return (outcome or OUTCOME_UNRESOLVED), row

    def _finalize_resolved(self, row, senses):
        if senses and not self._indexes.row_has_senses(row, senses):
            return OUTCOME_MISSING, None
        return OUTCOME_RESOLVED, row

    def _span_flags(self, block):
        try:
            root = ElementTree.fromstring(block)
        except ElementTree.ParseError:
            return self._span_flags_regex(block)

        regions = self._collect_regions(root)
        all_hws = [elem for elem in root.iter() if elem.tag == 'hw']
        entry_hw_texts = [''.join(hw.itertext()).strip() for hw in all_hws]
        entry_hw_ids = {hw.get(ATTR_ID) or '' for hw in all_hws}

        spans = []
        for region in regions.values():
            flags = self._region_flags(region, entry_hw_texts, entry_hw_ids)
            hw_norms = [
                row_norm(''.join(hw.itertext()).strip()) for hw in region['hw']
            ]
            spans.append((flags, hw_norms))
        return spans

    def _region_flags(self, region, entry_hw_texts, entry_hw_ids):
        flags = set()
        for see in region['see']:
            word, entry_attr, hw_attr = self._see_parts(see)
            outcome, _row = self._classify(word, entry_attr, hw_attr)
            flag = _OUTCOME_FLAGS.get(outcome)
            if flag:
                flags.add(flag)
        if len(region['hw']) >= _AMBIGUOUS_G_MIN_HW and len(region['g']) >= _AMBIGUOUS_G_MIN_G:
            unresolved_g = [
                g for g in region['g']
                if not self._g_resolved(g, entry_hw_texts, entry_hw_ids)
            ]
            if len(region['g']) == _SINGLE_REGION_G or unresolved_g:
                flags.add(MODE_AMBIGUOUS_G)
        return flags

    @staticmethod
    def _g_resolved(g_elem, entry_hw_texts, entry_hw_ids):
        attr = strip_quotes(g_elem.get(ATTR_HW) or '')
        if not attr:
            return False
        if attr in entry_hw_ids:
            return True
        if remove_accents(attr) != attr:
            return attr in entry_hw_texts
        target = remove_accents(attr)
        return any(remove_accents(text) == target for text in entry_hw_texts)

    def _span_flags_regex(self, block):
        flags = set()
        for match in _SEE_RE.finditer(block):
            word, entry_attr, hw_attr = self._see_parts_from_match(block, match)
            outcome, _row = self._classify(word, entry_attr, hw_attr)
            flag = _OUTCOME_FLAGS.get(outcome)
            if flag:
                flags.add(flag)
        if (len(re.findall(r'<hw\b', block)) >= _AMBIGUOUS_G_MIN_HW
                and len(re.findall(r'<g\b', block)) >= _AMBIGUOUS_G_MIN_G):
            flags.add(MODE_AMBIGUOUS_G)
        hw_norms = [
            row_norm(strip_tags(match.group(1)).strip())
            for match in HW_TEXT_RE.finditer(block)
        ]
        return [(flags, hw_norms)]
