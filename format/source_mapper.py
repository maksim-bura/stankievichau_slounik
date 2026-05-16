import json
import os
import re


class SourceMapper:
    _instance = None
    _variant_to_abbr = {}
    _sorted_variants = []
    _space_prefixed_only = {'акр.', 'п.', 'пав.', 'р.', 'с.', 'вол.'}
    _compiled_pattern = None

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
        with open(mapping_path, 'r', encoding='utf-8') as file:
            data = json.load(file)
        for mapping in data.get('mappings', []):
            abbr = mapping['abbr']
            for variant in mapping['variants']:
                self._variant_to_abbr[variant] = abbr
        self._sorted_variants = sorted(self._variant_to_abbr.keys(), key=len, reverse=True)
        self._compile_pattern()

    def _compile_pattern(self):
        escaped = [re.escape(variant) for variant in self._sorted_variants]
        self._compiled_pattern = re.compile('|'.join(escaped))

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
        matches = []
        for match in self._compiled_pattern.finditer(text):
            variant = match.group(0)
            if variant in self._space_prefixed_only:
                if match.start() > 0 and text[match.start() - 1] != ' ':
                    continue
            abbr = self._variant_to_abbr[variant]
            matches.append((abbr, variant))
        return matches


source_mapper = SourceMapper()
