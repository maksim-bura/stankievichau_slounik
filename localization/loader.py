import json
import os


class _StringsGroup:
    def __init__(self, data):
        self._data = data

    def __getattr__(self, key):
        if key in self._data:
            val = self._data[key]
            return _StringsGroup(val) if isinstance(val, dict) else val
        return f"[{key}]"


class Strings:
    _instance = None
    _strings = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load()
        return cls._instance

    def _load(self):
        json_path = os.path.join(os.path.dirname(__file__), 'strings.json')
        with open(json_path, 'r', encoding='utf-8') as file:
            self._strings = json.load(file)

    def get(self, key, default=None):
        return self._strings.get(key, default)

    def __getattr__(self, key):
        if key in self._strings:
            val = self._strings[key]
            return _StringsGroup(val) if isinstance(val, dict) else val
        return f"[{key}]"


strings = Strings()
