import json
import os


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
            return self._strings[key]
        return f"[{key}]"


strings = Strings()