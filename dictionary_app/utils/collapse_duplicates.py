from dictionary_app.utils.normalize_headword import resolve_headword


def collapse_with_identities(results):
    seen = set()
    collapsed = []
    identities = []
    for result in results:
        keep_acc = result[6] if len(result) > 6 else 0
        identity = resolve_headword(result[1], keep_acc)
        key = (result[0], identity)
        if key in seen:
            continue
        seen.add(key)
        collapsed.append(result)
        identities.append(identity)
    return collapsed, identities


def collapse_same_entry_duplicates(results):
    return collapse_with_identities(results)[0]
