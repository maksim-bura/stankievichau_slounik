import re
import xml.etree.ElementTree as ElementTree

from dictionary_app.utils.normalize_headword import resolve_headword
from dictionary_app.utils.remove_accents import remove_accents
from dictionary_app.utils.xml_schema import ATTR_N
from markup_app.services.link_text import normalize_headword, row_norm, strip_tags
from markup_app.utils.xml_patterns import ENTRY_ID_RE, EXCL_ATTR_RE, HW_ATTRS_TEXT_RE


def _index_add(index, key, value):
    existing = index.get(key)
    if existing is None:
        index[key] = value
    elif isinstance(existing, list):
        existing.append(value)
    else:
        index[key] = [existing, value]


def index_values(index, key):
    value = index.get(key)
    if value is None:
        return ()
    if isinstance(value, list):
        return value
    return (value,)


def _norm_sense_value(value):
    value = value.strip()
    if not value:
        return None
    if value.endswith('.'):
        value = value[:-1].strip()
    if value.isdigit():
        return ('num', int(value))
    return ('str', value)


def _main_headword(block):
    for match in HW_ATTRS_TEXT_RE.finditer(block):
        if EXCL_ATTR_RE.search(match.group(1)):
            continue
        return row_norm(strip_tags(match.group(2)).strip())
    return None


class LinkIndexes:
    def __init__(self, connection_provider, source_blocks_provider):
        self._connection = connection_provider
        self._source_blocks = source_blocks_provider
        self._rows_cache = None
        self._norm_index = None
        self._exact_index = None
        self._entry_senses = None
        self._entry_indexes = None
        self._row_index_cache = None

    def invalidate(self):
        self._rows_cache = None
        self._norm_index = None
        self._exact_index = None
        self._entry_senses = None
        self._entry_indexes = None
        self._row_index_cache = None

    def rows(self):
        if self._rows_cache is not None:
            return self._rows_cache
        cursor = self._connection().cursor()
        rows = []
        cursor.execute("SELECT id, headword, entry_link, hw_xml_id, keep_acc FROM dictionary")
        rows.extend(cursor.fetchall())
        cursor.execute(
            "SELECT main_entry_id, headword, link, hw_xml_id, keep_acc FROM sub_headwords"
        )
        rows.extend(cursor.fetchall())
        self._rows_cache = rows
        return rows

    def by_normalized_headword(self):
        if self._norm_index is not None:
            return self._norm_index
        index = {}
        for row in self.rows():
            index.setdefault(normalize_headword(row[1]), []).append(row)
        self._norm_index = index
        return index

    def by_exact_headword(self):
        if self._exact_index is not None:
            return self._exact_index
        index = {}
        for row in self.rows():
            index.setdefault(resolve_headword(row[1], row[4]), []).append(row)
        self._exact_index = index
        return index

    def row_indexes(self):
        if self._row_index_cache is not None:
            return self._row_index_cache
        raw_hw = {}
        norm_hw = {}
        raw_link = {}
        norm_link = {}
        by_hw_xml_id = {}
        by_entry = {}
        for i, (entry_id, headword, link, hw_xml_id, _keep_acc) in enumerate(
            self.rows()
        ):
            _index_add(by_entry, entry_id, i)
            _index_add(raw_hw, headword, i)
            _index_add(norm_hw, remove_accents(headword), i)
            if link:
                _index_add(raw_link, link, i)
                _index_add(norm_link, remove_accents(link), i)
            if hw_xml_id:
                _index_add(by_hw_xml_id, hw_xml_id, i)
        self._row_index_cache = {
            'raw_hw': raw_hw,
            'norm_hw': norm_hw,
            'raw_link': raw_link,
            'norm_link': norm_link,
            'hw_xml_id': by_hw_xml_id,
            'by_entry': by_entry,
        }
        return self._row_index_cache

    def entry_attr_ids(self, attr):
        rows = self.rows()
        index = self.row_indexes()
        if remove_accents(attr) != attr:
            hw_ids = index_values(index['raw_hw'], attr)
            link_ids = index_values(index['raw_link'], attr)
        else:
            hw_ids = index_values(index['norm_hw'], attr)
            link_ids = index_values(index['norm_link'], attr)
        ids = {rows[i][0] for i in hw_ids}
        ids.update(rows[i][0] for i in link_ids)
        return ids

    def hw_attr_indexes(self, attr):
        index = self.row_indexes()
        if remove_accents(attr) != attr:
            matched = set(index_values(index['raw_hw'], attr))
        else:
            matched = set(index_values(index['norm_hw'], attr))
        matched.update(index_values(index['hw_xml_id'], attr))
        return matched

    def hw_attr_rows(self, attr):
        rows = self.rows()
        return [rows[i] for i in sorted(self.hw_attr_indexes(attr))]

    def entry_id_indexes(self):
        if self._entry_indexes is not None:
            return self._entry_indexes
        cursor = self._connection().cursor()
        by_link = {}
        by_hw = {}
        cursor.execute("SELECT id, headword, entry_link, source_file FROM dictionary")
        for entry_id, headword, entry_link, source_file in cursor.fetchall():
            if entry_link:
                by_link.setdefault(
                    (source_file, normalize_headword(entry_link)), []
                ).append(entry_id)
            by_hw.setdefault((source_file, row_norm(headword)), []).append(entry_id)
        self._entry_indexes = (by_link, by_hw)
        return self._entry_indexes

    def entry_ids(self, block, source_file):
        by_link, by_hw = self.entry_id_indexes()
        match = ENTRY_ID_RE.search(block)
        if match:
            key = (source_file, normalize_headword(match.group(1)))
            candidates = by_link.get(key, [])
            if candidates:
                return candidates
        main_hw = _main_headword(block)
        if main_hw is None:
            return []
        return by_hw.get((source_file, main_hw), [])

    def entry_senses(self):
        if self._entry_senses is not None:
            return self._entry_senses
        entry_senses = {}
        for source_file, block in self._source_blocks():
            entry_ids = self.entry_ids(block, source_file)
            if not entry_ids:
                continue
            block_senses = self._block_sense_attrs(block)
            for entry_id in entry_ids:
                entry_senses[entry_id] = block_senses
        self._entry_senses = entry_senses
        return entry_senses

    def row_has_senses(self, row, senses):
        entry_senses = self.entry_senses().get(row[0])
        if not entry_senses:
            return False
        return all(('num', sense) in entry_senses for sense in senses)

    @staticmethod
    def _block_sense_attrs(block):
        try:
            root = ElementTree.fromstring(block)
        except ElementTree.ParseError:
            attrs = set()
            for match in re.finditer(
                r'<sense\b([^>]*?)>(.*?)</sense>', block, re.DOTALL
            ):
                attr = re.search(r'\bn\s*=\s*"([^"]*)"', match.group(1))
                if attr:
                    value = _norm_sense_value(attr.group(1))
                else:
                    n = re.search(r'<n\b[^>]*>(.*?)</n>', match.group(2))
                    value = _norm_sense_value(n.group(1)) if n else None
                if value is not None:
                    attrs.add(value)
            return attrs
        attrs = set()
        for sense in root.iter('sense'):
            value = (sense.get(ATTR_N) or '').strip()
            if value:
                attrs.add(_norm_sense_value(value))
                continue
            n = next((c for c in sense if c.tag == 'n'), None)
            if n is not None:
                attrs.add(
                    _norm_sense_value(''.join(n.itertext()).strip())
                )
        return attrs
