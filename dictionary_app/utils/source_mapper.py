import json
import os


class SourceMapper:
    _instance = None
    _variant_to_abbr = {}
    _sorted_variants = []
    _space_prefixed_only = {'акр.', 'п.', 'пав.', 'р.', 'с.', 'вол.'}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.load_mappings()
        return cls._instance

    def load_mappings(self):
        mapping_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'data', 'source_mappings.json'
        )
        try:
            with open(mapping_path, 'r', encoding='utf-8') as file:
                data = json.load(file)
            for mapping in data.get('mappings', []):
                abbr = mapping['abbr']
                for variant in mapping['variants']:
                    self._variant_to_abbr[variant] = abbr
            self._sorted_variants = sorted(self._variant_to_abbr.keys(), key=len, reverse=True)
        except Exception:
            self._variant_to_abbr = {}
            self._sorted_variants = []

    def get_abbreviation(self, source_text):
        if source_text in self._variant_to_abbr:
            return self._variant_to_abbr[source_text]
        for variant in self._sorted_variants:
            if variant in self._space_prefixed_only:
                if ' ' + variant in source_text or source_text.startswith(variant):
                    return self._variant_to_abbr[variant]
            else:
                if variant in source_text:
                    return self._variant_to_abbr[variant]
        return source_text

    def extract_abbreviations(self, text):
        results = []
        matched_positions = []
        for variant in self._sorted_variants:
            start = 0
            while True:
                start = text.find(variant, start)
                if start == -1:
                    break
                end = start + len(variant)
                overlap = False
                for m_start, m_end in matched_positions:
                    if not (end <= m_start or start >= m_end):
                        overlap = True
                        break
                if not overlap:
                    if variant in self._space_prefixed_only:
                        if start == 0 or text[start - 1] == ' ':
                            abbr = self._variant_to_abbr[variant]
                            results.append((abbr, variant, start, end))
                            matched_positions.append((start, end))
                    else:
                        abbr = self._variant_to_abbr[variant]
                        results.append((abbr, variant, start, end))
                        matched_positions.append((start, end))
                start = end
        return [(abbr, variant) for abbr, variant, start, end in results]


source_mapper = SourceMapper()