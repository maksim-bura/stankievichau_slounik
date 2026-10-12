import json
import os


class _Group:
    def __init__(self, data):
        self._data = data

    def __getattr__(self, key):
        if key in self._data:
            val = self._data[key]
            return _Group(val) if isinstance(val, dict) else val
        return f"[{key}]"


class _MarkupStrings:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            path = os.path.join(os.path.dirname(__file__), 'strings.json')
            with open(path, 'r', encoding='utf-8') as file:
                cls._instance._data = json.load(file)
        return cls._instance

    def __getattr__(self, key):
        if key in self._data:
            val = self._data[key]
            return _Group(val) if isinstance(val, dict) else val
        return f"[{key}]"


strings = _MarkupStrings()