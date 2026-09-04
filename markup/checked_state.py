import json
import os


class CheckedState:
    def __init__(self):
        self._path = os.path.join(
            os.path.dirname(__file__), '..', 'build', 'markup_checked.json'
        )
        self._states = {}
        self._load()

    def _load(self):
        if os.path.exists(self._path):
            with open(self._path, 'r', encoding='utf-8') as f:
                self._states = json.load(f)
        else:
            self._states = {}

    def save(self):
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        with open(self._path, 'w', encoding='utf-8') as f:
            json.dump(self._states, f, ensure_ascii=False, indent=2)

    def _key(self, entry_id, headword):
        return f'{entry_id}:{headword}'

    def is_checked(self, entry_id, headword):
        return self._states.get(self._key(entry_id, headword), False)

    def toggle(self, entry_id, headword):
        key = self._key(entry_id, headword)
        self._states[key] = not self._states.get(key, False)
        self.save()
        return self._states[key]

    def set_checked(self, entry_id, headword, value):
        self._states[self._key(entry_id, headword)] = value
        self.save()

    def get_all_checked(self):
        return {k: v for k, v in self._states.items() if v}
