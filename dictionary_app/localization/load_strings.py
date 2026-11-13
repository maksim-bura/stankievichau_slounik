import json
import os


REF_KEY = '$ref'


class StringsGroup:
    def __init__(self, data, owner):
        self._data = data
        self._owner = owner

    def __getattr__(self, key):
        return self._owner._lookup(self._data, key)


class Strings:
    def __init__(self, base_dir, filename, shared=None):
        self._base_dir = base_dir
        self._filename = filename
        self._shared = shared or {}
        self._strings = {}
        self._load()

    def _load(self):
        path = os.path.join(self._base_dir, self._filename)
        with open(path, 'r', encoding='utf-8') as file:
            self._strings = json.load(file)

    def _resolve_ref(self, ref):
        if ':' in ref:
            source_name, _, key_path = ref.partition(':')
            source = self._shared.get(source_name)
            if source is None:
                return f'[{ref}]'
        else:
            key_path = ref
            source = self
        node = source._strings if isinstance(source, Strings) else source
        for part in key_path.split('.'):
            if not isinstance(node, dict) or part not in node:
                return f'[{ref}]'
            node = node[part]
        if isinstance(node, dict):
            if REF_KEY in node:
                return self._resolve_ref(node[REF_KEY])
            return StringsGroup(node, source)
        return node

    def _lookup(self, data, key):
        if key not in data:
            return f'[{key}]'
        value = data[key]
        if isinstance(value, dict):
            ref = value.get(REF_KEY)
            if isinstance(ref, str):
                return self._resolve_ref(ref)
            return StringsGroup(value, self)
        return value

    def __getattr__(self, key):
        return self._lookup(self._strings, key)


def load_strings(base_dir, filename, shared=None):
    return Strings(base_dir, filename, shared)
