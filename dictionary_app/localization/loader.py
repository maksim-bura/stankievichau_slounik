import json
import os


class StringsGroup:
    def __init__(self, data):
        self._data = data

    def __getattr__(self, key):
        if key in self._data:
            value = self._data[key]
            return StringsGroup(value) if isinstance(value, dict) else value
        return f'[{key}]'


class Strings:
    def __init__(self, base_dir, files):
        self._base_dir = base_dir
        self._files = files
        self._strings = {}
        self._load()

    def _load(self):
        self._strings = {}
        for name in self._files:
            path = os.path.join(self._base_dir, name)
            with open(path, 'r', encoding='utf-8') as file:
                self._strings.update(json.load(file))

    def get(self, key, default=None):
        return self._strings.get(key, default)

    def __getattr__(self, key):
        if key in self._strings:
            value = self._strings[key]
            return StringsGroup(value) if isinstance(value, dict) else value
        return f'[{key}]'


def load_strings(base_dir, *files):
    return Strings(base_dir, files)
