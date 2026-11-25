import json
import os
from dictionary_app.utils.remove_accents import remove_accents


class CheckedState:
    def __init__(self):
        self._path = os.path.join(
            os.path.dirname(__file__), 'build', 'markup_checked.json'
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

    def _key(self, source_file, entry_id, entry_link, headword, occurrence):
        return (
            f'{source_file}:{entry_id}:{entry_link}:{headword}:{occurrence}'
        )

    def is_checked(self, source_file, entry_id, entry_link, headword, occurrence):
        return self._states.get(
            self._key(
                source_file, entry_id, entry_link, headword, occurrence),
            False,
        )

    def toggle(self, source_file, entry_id, entry_link, headword, occurrence):
        key = self._key(
            source_file, entry_id, entry_link, headword, occurrence)
        self._states[key] = not self._states.get(key, False)
        self.save()
        return self._states[key]

    def uncheck_all(self):
        self._states.clear()
        self.save()

    def remove_entry(self, source_file, entry_id):
        prefix = f'{source_file}:{entry_id}:'
        removed = [
            key for key in self._states if key.startswith(prefix)
        ]
        if not removed:
            return
        for key in removed:
            del self._states[key]
        self.save()

    def migrate(self, conn):
        if not self._states:
            return
        try:
            dict_rows = conn.execute(
                "SELECT id, headword, entry_link, source_file FROM dictionary"
            ).fetchall()
            sub_rows = conn.execute(
                "SELECT main_entry_id, sub_headwords.headword, "
                "dictionary.entry_link, dictionary.source_file "
                "FROM sub_headwords "
                "JOIN dictionary ON sub_headwords.main_entry_id = dictionary.id"
            ).fetchall()
        except Exception:
            return

        rows = list(dict_rows) + list(sub_rows)
        by_id = {
            row[0]: row[1:] for row in dict_rows
        }
        by_parts = {}
        by_src_hw = {}
        for row in rows:
            entry_id, headword, entry_link, source_file = row
            by_parts.setdefault(
                (source_file, entry_link, headword), []
            ).append(row)
            by_src_hw.setdefault(
                (source_file, headword), []
            ).append(row)

        def current(row, occurrence=0):
            entry_id, headword, entry_link, source_file = row
            return self._key(
                source_file, entry_id, entry_link, headword, occurrence)

        def parse_current(key):
            tail, sep, occurrence = key.rpartition(':')
            if not sep or not occurrence.isdigit():
                return None
            source_file, sep, rest = tail.partition(':')
            if not sep:
                return None
            entry_id_text, sep, rest = rest.partition(':')
            if not sep or not entry_id_text.isdigit():
                return None
            entry_link, sep, headword = rest.partition(':')
            if not sep:
                return None
            link = None if entry_link == 'None' else entry_link
            return (
                source_file, link, headword, int(entry_id_text),
                int(occurrence),
            )

        def rekey(parsed):
            source_file, link, headword, entry_id, occurrence = parsed
            candidates = by_parts.get((source_file, link, headword))
            if not candidates:
                return None
            for row in candidates:
                if row[0] == entry_id:
                    return current(row, occurrence)
            if len(candidates) == 1:
                return current(candidates[0], occurrence)
            return None

        ambiguous = {}
        for key in self._states:
            parsed = parse_current(key)
            if parsed is None:
                continue
            source_file, link, headword, entry_id, occurrence = parsed
            candidates = by_parts.get((source_file, link, headword))
            if not candidates or len(candidates) < 2:
                continue
            if any(row[0] == entry_id for row in candidates):
                continue
            ambiguous.setdefault(
                (source_file, link, headword), []
            ).append((entry_id, occurrence, key))

        ranked = {}
        for group, keys in ambiguous.items():
            candidates = sorted(by_parts[group], key=lambda row: row[0])
            if len(keys) != len(candidates):
                continue
            for (_, occurrence, key), row in zip(sorted(keys), candidates):
                ranked[key] = current(row, occurrence)

        def rewrite(key):
            parts = key.split(':')
            if (
                len(parts) >= 5
                and parts[1].isdigit()
                and parts[-1].isdigit()
            ):
                return [key]
            if len(parts) >= 4 and parts[1].isdigit():
                entry_id = int(parts[1])
                tail = key.split(':', 3)[3]
                for row in rows:
                    if row[0] != entry_id:
                        continue
                    if tail == f'{row[2]}:{row[1]}':
                        return [current(row)]
                return None
            if parts[0].isdigit():
                entry_id = int(parts[0])
                if entry_id not in by_id:
                    return None
                headword, entry_link, source_file = by_id[entry_id]
                rest = key.partition(':')[2]
                if rest and remove_accents(rest) != remove_accents(headword):
                    return None
                return [current((entry_id, headword, entry_link, source_file))]
            if ':' not in key:
                return None
            source_file, _, rest = key.partition(':')
            if (source_file, rest) in by_src_hw:
                return [current(row) for row in by_src_hw[(source_file, rest)]]
            entry_link, sep, headword = rest.rpartition(':')
            if not sep:
                return None
            link = None if entry_link == 'None' else entry_link
            matches = by_parts.get((source_file, link, headword))
            if not matches:
                matches = [
                    row for row in rows
                    if row[3] == source_file
                    and row[2] == link
                    and remove_accents(row[1]) == remove_accents(headword)
                ]
            if not matches:
                return None
            return [current(row) for row in matches]

        migrated = {}
        changed = False
        for key, value in self._states.items():
            new_key = ranked.get(key)
            if new_key is None:
                parsed = parse_current(key)
                if parsed is not None:
                    new_key = rekey(parsed)
            if new_key is not None:
                if new_key != key:
                    changed = True
                migrated[new_key] = migrated.get(new_key, False) or value
                continue
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
