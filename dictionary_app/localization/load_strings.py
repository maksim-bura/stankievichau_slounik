import json
import os


def _lookup(data, key):
    if key in data:
        value = data[key]
        return StringsGroup(value) if isinstance(value, dict) else value
    return f'[{key}]'


class StringsGroup:
    def __init__(self, data):
        self._data = data

    def __getattr__(self, key):
        return _lookup(self._data, key)


class Strings:
    def __init__(self, base_dir, filename):
        self._base_dir = base_dir
        self._filename = filename
        self._strings = {}
        self._load()

    def _load(self):
        path = os.path.join(self._base_dir, self._filename)
        with open(path, 'r', encoding='utf-8') as file:
            self._strings = json.load(file)

    def __getattr__(self, key):
        return _lookup(self._strings, key)


def load_strings(base_dir, filename):
    return Strings(base_dir, filename)
