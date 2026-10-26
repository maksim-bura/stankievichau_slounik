from dictionary_app.utils.normalize_headword import resolve_headword


def all_ids_resolved(member_ids):
    seen = set()
    for ids in member_ids:
        if not ids:
            return False
        for i in ids:
            if i in seen:
                return False
            seen.add(i)
    return True


class DuplicateResolver:
    def __init__(self, search_engine):
        self._search_engine = search_engine
        self._lookup_cache = None

    def invalidate(self):
        self._lookup_cache = None

    def filter(self, results):
        by_norm = {}
        for r in results:
            by_norm.setdefault(resolve_headword(r[1], r[6] if len(r) > 6 else 0), []).append(r)

        unresolved = []
        for rows in by_norm.values():
            if len(rows) >= 2 and not self._is_resolved_duplicates(rows):
                unresolved.extend(rows)
        return unresolved

    def _tables(self):
        if self._lookup_cache is None:
            dict_rows_raw, sub_rows = self._search_engine.fetch_link_target_rows()
            dict_rows = {row[0]: row[1:] for row in dict_rows_raw}
            sub_by_key = {}
            for main_id, headword, link, hw_xml_id in sub_rows:
                sub_by_key.setdefault((main_id, headword, link), []).append(hw_xml_id)
            self._lookup_cache = (dict_rows, sub_by_key)
        return self._lookup_cache

    def _is_resolved_duplicates(self, rows):
        if len(rows) < 2:
            return False
        dict_rows, sub_by_key = self._tables()

        member_ids = []
        for r in rows:
            info = dict_rows.get(r[0])
            if info is not None and info[0] == r[1]:
                ids = {i for i in (info[1], info[2]) if i}
            else:
                ids = {i for i in (r[3],) if i}
                for hw_id in sub_by_key.get((r[0], r[1], r[3]), ()):
                    if hw_id:
                        ids.add(hw_id)
            member_ids.append(ids)

        return all_ids_resolved(member_ids)
