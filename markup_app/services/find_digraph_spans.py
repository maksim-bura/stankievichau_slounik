from markup_app.utils.xml_patterns import HW_TEXT_RE


_DIGRAPHS = frozenset({'дз', 'дж'})


def find_digraph_spans(text):
    spans = []
    for match in HW_TEXT_RE.finditer(text):
        content_start = match.start(1)
        content = match.group(1)
        for index in range(len(content) - 1):
            if content[index:index + 2].lower() in _DIGRAPHS:
                spans.append((content_start + index, content_start + index + 2))
    return spans
