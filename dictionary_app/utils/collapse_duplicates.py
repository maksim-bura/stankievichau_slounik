from dictionary_app.utils.normalize_headword import resolve_headword


def collapse_same_entry_duplicates(results):
    seen = set()
    collapsed = []
    for result in results:
        keep_acc = result[6] if len(result) > 6 else 0
        key = (result[0], resolve_headword(result[1], keep_acc))
        if key in seen:
            continue
        seen.add(key)
        collapsed.append(result)
    return collapsed
