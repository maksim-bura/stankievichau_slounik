import json
import os
from utils.text_utils import remove_accents


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
                content = f.read()
            if not content.strip():
                self._states = {}
            else:
                try:
                    self._states = json.loads(content)
                except json.JSONDecodeError:
                    backup = f'{self._path}.bak'
                    with open(backup, 'w', encoding='utf-8') as f:
                        f.write(content)
                    self._states = {}
        else:
            self._states = {}

    def save(self):
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        with open(self._path, 'w', encoding='utf-8') as f:
            json.dump(self._states, f, ensure_ascii=False, indent=2)

    def _key(self, source_file, entry_link, headword):
        return f'{source_file}:{entry_link}:{headword}'

    def is_checked(self, source_file, entry_link, headword):
        return self._states.get(self._key(source_file, entry_link, headword), False)

    def toggle(self, source_file, entry_link, headword):
        key = self._key(source_file, entry_link, headword)
        self._states[key] = not self._states.get(key, False)
        self.save()
        return self._states[key]

    def set_checked(self, source_file, entry_link, headword, value):
        self._states[self._key(source_file, entry_link, headword)] = value
        self.save()

    def get_all_checked(self):
        return {k: v for k, v in self._states.items() if v}

    def migrate(self, conn):
        try:
            rows = conn.execute(
                "SELECT id, headword, entry_link, source_file FROM dictionary"
            ).fetchall()
        except Exception:
            return
        by_id = {row[0]: (row[1], row[2], row[3]) for row in rows}
        by_src_hw = {}
        for rowid, headword, entry_link, source_file in rows:
            by_src_hw.setdefault((source_file, headword), set()).add(entry_link)

        def resolve(headword, entry_link, source_file):
            return self._key(source_file, entry_link, headword)

        def rewrite(key):
            if ':' not in key:
                if key.isdigit() and int(key) in by_id:
                    hw, link, src = by_id[int(key)]
                    return [resolve(hw, link, src)]
                return None
            first, _, rest = key.partition(':')
            if first.isdigit():
                if int(first) not in by_id:
                    return None
                hw, link, src = by_id[int(first)]
                if remove_accents(rest) == remove_accents(hw):
                    return [resolve(hw, link, src)]
                return None
            source_file = first
            if (source_file, rest) in by_src_hw:
                links = by_src_hw[(source_file, rest)]
                return [resolve(rest, link, source_file) for link in links]
            return None

        migrated = {}
        changed = False
        for key, value in self._states.items():
            new_keys = rewrite(key)
            if new_keys is None:
                migrated[key] = value
                continue
            for nk in new_keys:
                if nk != key:
                    changed = True
                migrated[nk] = migrated.get(nk, False) or value
        if changed:
            self._states = migrated
            self.save()
