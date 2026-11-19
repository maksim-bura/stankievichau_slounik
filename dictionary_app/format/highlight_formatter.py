import re

from dictionary_app.utils.normalize_headword import normalize_jo_to_je


EXCLUDED_HIGHLIGHT_CLASS = 'search-excluded'
PARAGRAPH_BREAK_KEY = 'paragraph_break'

_ANCHOR_RANGE_RE = re.compile(r'(<a\s[^>]*>.*?</a>)', re.DOTALL)
_SAVED_BLOCK_PLACEHOLDER_RE = re.compile(r'\x00A(\d+)\x00')
_RESTORE_PASSES = 2


class HighlightFormatter:
    def apply_highlight(self, formatted_html, pattern, normalize=True, exclude_classes=None):
        all_saved = []
        protected = formatted_html

        def _save_a(m):
            all_saved.append(m.group(1))
            return f'\x00A{len(all_saved)-1}\x00'
        protected = _ANCHOR_RANGE_RE.sub(_save_a, protected)

        if exclude_classes:
            for cls in exclude_classes:
                protected = self._protect_class_blocks(protected, cls, all_saved)

        parts = re.split(r'(<[^>]*>)', protected)

        expanded = []
        for part in parts:
            if not part.startswith('<') and '\x00' in part:
                for chunk in re.split(r'(\x00[^\x00]*\x00)', part):
                    if chunk:
                        expanded.append(chunk)
            else:
                expanded.append(part)
        parts = expanded

        text_ranges = []
        concat_pos = 0
        for i, part in enumerate(parts):
            if not part.startswith('<') and part and '\x00' not in part:
                text_ranges.append((concat_pos, i))
                concat_pos += len(part)

        if not text_ranges:
            return _restore_saved_blocks(''.join(parts), all_saved)

        concatenated = ''.join(parts[r[1]] for r in text_ranges)
        normalized = normalize_jo_to_je(concatenated) if normalize else concatenated

        matches = list(pattern.finditer(normalized))

        highlights_per_part = {}
        for m in matches:
            ms, me = m.start(), m.end()
            for concat_start, part_idx in text_ranges:
                part_len = len(parts[part_idx])
                concat_end = concat_start + part_len
                if me <= concat_start or ms >= concat_end:
                    continue
                local_start = max(ms - concat_start, 0)
                local_end = min(me - concat_start, part_len)
                highlights_per_part.setdefault(part_idx, []).append((local_start, local_end))

        for part_idx, ranges in highlights_per_part.items():
            ranges.sort()
            merged = []
            for s, e in ranges:
                if merged and s <= merged[-1][1]:
                    merged[-1] = (merged[-1][0], max(merged[-1][1], e))
                else:
                    merged.append((s, e))
            part = parts[part_idx]
            result_parts = []
            last = 0
            for s, e in merged:
                result_parts.append(part[last:s])
                result_parts.append(
                    f'<span class="search-highlight">{part[s:e]}</span>'
                )
                last = e
            result_parts.append(part[last:])
            parts[part_idx] = ''.join(result_parts)

        return _restore_saved_blocks(''.join(parts), all_saved)

    def _protect_class_blocks(self, html, class_name, saved_list):
        pattern = re.compile(
            r'(<span[^>]*class="[^"]*' + re.escape(class_name) + r'[^"]*"[^>]*>)'
        )
        result = []
        pos = 0
        while pos < len(html):
            m = pattern.search(html, pos)
            if not m:
                result.append(html[pos:])
                break
            result.append(html[pos:m.start()])
            start = m.start()
            depth = 1
            i = m.end()
            while depth > 0 and i < len(html):
                next_open = html.find('<span', i)
                next_close = html.find('</span>', i)
                if next_close == -1:
                    i = len(html)
                    break
                if next_open != -1 and next_open < next_close:
                    depth += 1
                    i = next_open + len('<span')
                else:
                    depth -= 1
                    i = next_close + len('</span>')
            saved_list.append(html[start:i])
            result.append(f'\x00A{len(saved_list)-1}\x00')
            pos = i
        return ''.join(result)


def _restore_saved_blocks(html, saved_blocks):
    if not saved_blocks:
        return html
    for _ in range(_RESTORE_PASSES):
        html = _SAVED_BLOCK_PLACEHOLDER_RE.sub(
            lambda m: saved_blocks[int(m.group(1))], html
        )
    return html
