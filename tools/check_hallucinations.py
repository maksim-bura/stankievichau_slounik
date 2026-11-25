import argparse
import difflib
import hashlib
import json
import re
import sys
import xml.etree.ElementTree as ElementTree
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DICTIONARY_DIR = PROJECT_ROOT / 'dictionary_app' / 'data' / 'dictionary'
RAW_DIR = PROJECT_ROOT / 'markup_app' / 'data' / 'dictionary_raw'
STATE_PATH = PROJECT_ROOT / 'tools' / 'build' / 'hallucination_state.json'
XML_PREFIX = 'dictionary_'
XML_SUFFIX = '.xml'
RAW_SUFFIX = '_raw.txt'
ACUTE = '\u0301'
GRAVE = '\u0300'
BULLET = '\u2022'
ACCENTS = str.maketrans('', '', ACUTE + GRAVE)
WORD = re.compile(r'[^\W_]+', re.UNICODE)
ENTRY = re.compile(r'<entry\b')
TEXT_TAGS = frozenset(('hw', 't', 'ex', 'src', 'st', 'g', 'i', 'see', 'lang'))
LABEL_TEXTS = (
    'Соверш.', 'Прич.', 'Уменьш.', 'Отгл. имя сущ.', 'Однкр.', 'Нареч.',
    'Многократ.', 'Несоверш.', 'Ср. ст.', 'Увелич.', 'Единств. ч.', 'Нв.',
    'Прев. ст.', 'Собир.', 'Одна:', 'Возвр.', 'один', 'Прилаг. из прич.',
    'ср ст.', 'Прич. наст. вр.', 'соверш.', 'Ласкат.', 'мн. ч.',
)
MATCH_THRESHOLD = 0.72
LABEL_THRESHOLD = 0.60
ORDER_THRESHOLD = 0.65
BLOCK_THRESHOLD = 0.55
SOURCE_TAIL = 220
MATCH_CHARS = 4000
LOOKAHEAD = 5
SNIPPET = 110
STATE_VERSION = 1


def normalize(text):
    text = text.translate(ACCENTS).lower().replace('ё', 'е')
    return ' '.join(WORD.findall(text))


KNOWN_LABELS = frozenset(normalize(text) for text in LABEL_TEXTS)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--letter', default='')
    parser.add_argument('--headword', default='')
    parser.add_argument('--all', action='store_true')
    parser.add_argument('--changed', action='store_true')
    parser.add_argument('--force', action='store_true')
    parser.add_argument('--reset', action='store_true')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--state', default=str(STATE_PATH))
    parser.add_argument('--report', default='')
    parser.add_argument('--limit', type=int, default=20)
    return parser.parse_args()


def word_text(element):
    return ''.join(element.itertext()).strip()


def main_headword(entry):
    fallback = ''
    for element in entry.iter('hw'):
        text = word_text(element)
        if 'excl' not in element.attrib:
            return text
        fallback = fallback or text
    return fallback


def headword_texts(entry):
    return [word_text(element) for element in entry.iter('hw')]


def text_runs(element, current=None):
    if element.tag in TEXT_TAGS:
        current = element.tag
    if element.text:
        yield current, element.text
    for child in element:
        yield from text_runs(child, current)
        if child.tail:
            yield current, child.tail


def entry_text(entry):
    return normalize(''.join(entry.itertext()))


def fingerprint(entry):
    payload = ElementTree.tostring(entry, encoding='unicode')
    return hashlib.sha1(payload.encode('utf-8')).hexdigest()


def entry_key(entry, occurrence):
    identifier = entry.get('id')
    if identifier:
        return 'id:' + identifier
    return 'hw:%s#%d' % (normalize(main_headword(entry)), occurrence)


def entry_lines(xml_text):
    return [xml_text.count('\n', 0, match.start()) + 1
            for match in ENTRY.finditer(xml_text)]


def load_state(path):
    if not path.exists():
        return {'version': STATE_VERSION, 'files': {}}
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {'version': STATE_VERSION, 'files': {}}
    if not isinstance(data, dict) or data.get('version') != STATE_VERSION:
        return {'version': STATE_VERSION, 'files': {}}
    if not isinstance(data.get('files'), dict):
        data['files'] = {}
    return data


def save_state(path, state):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True),
                         encoding='utf-8')
    temporary.replace(path)


def discover_pairs(letter):
    pairs = []
    for xml_path in sorted(DICTIONARY_DIR.glob(XML_PREFIX + '*' + XML_SUFFIX)):
        name = xml_path.stem[len(XML_PREFIX):]
        if letter and name.lower() != letter.lower():
            continue
        raw_path = RAW_DIR / (XML_PREFIX + name + RAW_SUFFIX)
        pairs.append((name, xml_path, raw_path))
    return pairs


def coverage(needle, haystack):
    matcher = difflib.SequenceMatcher(None, needle, haystack, autojunk=False)
    matched = sum(block.size for block in matcher.get_matching_blocks())
    return matched / len(needle)


def locate(needle, haystack, threshold, start=0, wrap=True):
    if not needle:
        return True, 1.0, start
    position = haystack.find(needle, start)
    if position >= 0:
        return True, 1.0, position
    tail = haystack[start:]
    matcher = difflib.SequenceMatcher(None, needle, tail, autojunk=False)
    block = matcher.find_longest_match(0, len(needle), 0, len(tail))
    if block.size:
        offset = max(0, block.b - block.a)
        candidate = tail[max(0, offset - 10):offset + len(needle) + 10]
        score = coverage(needle, candidate)
        required = threshold if len(needle) >= 5 else min(1.0, threshold + 0.2)
        if score >= required:
            return True, score, start + offset
    if start and wrap:
        return locate(needle, haystack, threshold)
    return False, 0.0, -1


def similarity(left, right):
    return difflib.SequenceMatcher(
        None, left[:MATCH_CHARS], right[:MATCH_CHARS], autojunk=False).ratio()


def read_raw_blocks(raw_text):
    starts = [index for index, char in enumerate(raw_text) if char == BULLET]
    blocks = []
    for position, start in enumerate(starts):
        end = starts[position + 1] if position + 1 < len(starts) else len(raw_text)
        body = raw_text[start:end]
        blocks.append({
            'line': raw_text.count('\n', 0, start) + 1,
            'text': normalize(body.replace(BULLET, '', 1)),
        })
    return blocks


def align_blocks(records, blocks):
    anchors = []
    position = 0
    for entry, _key, _value in records:
        text = entry_text(entry)
        best = None
        best_score = 0.0
        for offset in range(LOOKAHEAD):
            candidate = position + offset
            if candidate >= len(blocks):
                break
            score = similarity(text, blocks[candidate]['text'])
            if score > best_score:
                best_score = score
                best = candidate
        if best is None or best_score < BLOCK_THRESHOLD:
            anchors.append(None)
            continue
        anchors.append(best)
        position = best + 1
    return anchors


def add_finding(findings, file_name, line, headword, rule, severity, snippet,
                raw_line, raw_snippet, score, detail):
    key = (file_name, line, headword, rule, detail, snippet)
    finding = {
        'file': file_name,
        'line': line,
        'headword': headword,
        'rule': rule,
        'severity': severity,
        'xml': snippet,
        'raw_line': raw_line,
        'raw': raw_snippet,
        'score': round(score, 3),
        'detail': detail,
    }
    existing = findings.get(key)
    if existing is None or (existing['severity'] == 'review' and severity == 'violation'):
        findings[key] = finding


def check_labels(entry, raw_norm, findings, file_name, line, headword, raw_line):
    for parent in entry.iter():
        children = list(parent)
        for index, child in enumerate(children):
            if child.tag != 'hw' or index == 0:
                continue
            label_element = children[index - 1]
            if label_element.tag != 'g':
                continue
            label = word_text(label_element)
            if label.startswith('-'):
                continue
            label_norm = normalize(label)
            if not label_norm:
                continue
            ok, score, _ = locate(label_norm, raw_norm, LABEL_THRESHOLD)
            if not ok:
                add_finding(findings, file_name, line, headword, 'grammar-label', 'violation',
                            label, raw_line, raw_norm[:SNIPPET], score, 'label not in raw')
            elif label_norm not in KNOWN_LABELS:
                add_finding(findings, file_name, line, headword, 'grammar-label', 'review',
                            label, raw_line, raw_norm[:SNIPPET], score, 'unrecognized label')


def check_ex_sources(entry, raw_norm, findings, file_name, line, headword, raw_line):
    for example in entry.iter('ex'):
        example_norm = normalize(' '.join(
            text for tag, text in text_runs(example) if tag != 'src'))
        sources = [child for child in example if child.tag == 'src']
        if not example_norm or not sources:
            continue
        ok, score, position = locate(example_norm, raw_norm, MATCH_THRESHOLD)
        if not ok:
            continue
        tail = raw_norm[position + len(example_norm):position + len(example_norm) + SOURCE_TAIL]
        for source in sources:
            source_norm = normalize(word_text(source))
            if not source_norm:
                continue
            found, source_score, _ = locate(source_norm, tail, LABEL_THRESHOLD)
            if found:
                continue
            present, present_score, _ = locate(source_norm, raw_norm, LABEL_THRESHOLD)
            detail = 'source elsewhere in raw' if present else 'source absent from raw'
            severity = 'review'
            if not present and source_norm.isalpha() and len(source_norm) <= 5:
                severity = 'violation'
            add_finding(findings, file_name, line, headword, 'source-after-example',
                        severity, word_text(example),
                        raw_line, raw_norm[:SNIPPET],
                        present_score if present else source_score, detail)


def check_order(entry, raw_norm, findings, file_name, line, headword, raw_line):
    cursor = 0
    for tag, text in text_runs(entry):
        if tag is None:
            continue
        needle = normalize(text)
        if not needle:
            continue
        ok, score, position = locate(needle, raw_norm, ORDER_THRESHOLD, cursor, wrap=False)
        if not ok:
            continue
        if position < cursor:
            add_finding(findings, file_name, line, headword, 'element-order', 'review',
                        text, raw_line, raw_norm[max(0, position):position + SNIPPET],
                        score, 'out of raw order')
        cursor = position + len(needle)


def check_entry(entry, raw_window, raw_line, findings, file_name, line):
    headword = main_headword(entry)
    check_labels(entry, raw_window, findings, file_name, line, headword, raw_line)
    check_ex_sources(entry, raw_window, findings, file_name, line, headword, raw_line)
    check_order(entry, raw_window, findings, file_name, line, headword, raw_line)
    for tag, text in text_runs(entry):
        if tag is None:
            continue
        needle = normalize(text)
        if not needle:
            continue
        ok, score, _ = locate(needle, raw_window, MATCH_THRESHOLD, wrap=False)
        if ok:
            continue
        strong = tag not in ('src', 'g') and len(needle) >= 20 and score < 0.40
        add_finding(findings, file_name, line, headword, 'unmatched-content',
                    'violation' if strong else 'review', text, raw_line,
                    raw_window[:SNIPPET], score, tag)


def write_report(path, findings, summary):
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Font, PatternFill
        from openpyxl.utils import get_column_letter
    except ImportError:
        print('openpyxl is not installed; skipping the Excel report', file=sys.stderr)
        return
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = 'Findings'
    headers = ['Severity', 'File', 'XML line', 'Headword', 'Rule', 'XML snippet',
               'Raw line', 'Raw snippet', 'Score', 'Detail']
    sheet.append(headers)
    for cell in sheet[1]:
        cell.font = Font(bold=True, color='FFFFFF')
        cell.fill = PatternFill('solid', fgColor='1F4E78')
        cell.alignment = Alignment(wrap_text=True, vertical='center')
    for finding in findings:
        sheet.append([finding['severity'], finding['file'], finding['line'],
                      finding['headword'], finding['rule'], finding['xml'],
                      finding['raw_line'], finding['raw'], finding['score'],
                      finding['detail']])
    for row in sheet.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = Alignment(wrap_text=True, vertical='top')
    widths = [10, 30, 8, 18, 22, 45, 8, 45, 8, 28]
    for index, width in enumerate(widths, 1):
        sheet.column_dimensions[get_column_letter(index)].width = width
    sheet.freeze_panes = 'A2'
    sheet.auto_filter.ref = sheet.dimensions
    summary_sheet = workbook.create_sheet('Summary')
    summary_sheet.append(['Item', 'Value'])
    for key, value in summary.items():
        summary_sheet.append([key, value])
    summary_sheet.column_dimensions['A'].width = 28
    summary_sheet.column_dimensions['B'].width = 90
    for row in summary_sheet.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = Alignment(wrap_text=True, vertical='top')
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(path)


def main():
    args = parse_args()
    if not (args.all or args.changed or args.letter or args.headword):
        print('explicit scope required: pass --all, --changed, --letter, or --headword',
              file=sys.stderr)
        print('confirm the checked delta with the user before auditing', file=sys.stderr)
        return 2
    state = load_state(Path(args.state))
    if args.reset:
        state = {'version': STATE_VERSION, 'files': {}}
    findings = {}
    audited = 0
    skipped = 0
    files = discover_pairs(args.letter)
    for name, xml_path, raw_path in files:
        if not raw_path.exists():
            continue
        xml_text = xml_path.read_text(encoding='utf-8')
        root = ElementTree.parse(xml_path).getroot()
        lines = entry_lines(xml_text)
        raw_text = raw_path.read_text(encoding='utf-8-sig')
        blocks = read_raw_blocks(raw_text)
        previous = state['files'].get(xml_path.name, {})
        occurrences = {}
        records = []
        for entry in root.iter('entry'):
            word = normalize(main_headword(entry))
            key = entry_key(entry, occurrences.get(word, 0))
            occurrences[word] = occurrences.get(word, 0) + 1
            records.append((entry, key, fingerprint(entry)))
        current = {key: value for _, key, value in records}
        retained = {key: value for key, value in previous.items() if key in current}
        anchors = align_blocks(records, blocks)
        target = normalize(args.headword)
        for index, (entry, key, value) in enumerate(records):
            if target and target not in normalize(main_headword(entry)):
                continue

            if not args.all and not args.force and previous.get(key) == value:
                skipped += 1
                continue
            line = lines[index] if index < len(lines) else 0
            block_index = anchors[index]
            if block_index is None:
                add_finding(findings, xml_path.name, line, main_headword(entry),
                            'raw-window', 'review', entry_text(entry)[:SNIPPET], 0,
                            '', 0.0, 'no raw block matched the entry')
            else:
                block = blocks[block_index]
                check_entry(entry, block['text'], block['line'],
                            findings, xml_path.name, line)
            retained[key] = value
            audited += 1
        state['files'][xml_path.name] = retained
    ordered = sorted(findings.values(), key=lambda item: (
        0 if item['severity'] == 'violation' else 1, item['file'], item['line']))
    limit = len(ordered) if args.limit <= 0 else args.limit
    for finding in ordered[:limit]:
        print('[%s] %s:%s %s — %s (score %.3f, raw %s)' % (
            finding['severity'].upper(), finding['file'], finding['line'],
            finding['headword'], finding['rule'], finding['score'], finding['raw_line']))
        print('  xml: %s' % finding['xml'])
        print('  raw: %s' % finding['raw'])
    violations = sum(1 for item in ordered if item['severity'] == 'violation')
    reviews = len(ordered) - violations
    print('audited %d entries, skipped %d, findings %d (%d violations, %d review)' % (
        audited, skipped, len(ordered), violations, reviews))
    if args.report and ordered:
        report = Path(args.report)
        summary = {
            'audited entries': audited,
            'skipped entries': skipped,
            'findings': len(ordered),
            'violations': violations,
            'review': reviews,
            'mode': 'all' if args.all else ('changed' if args.changed else 'scoped'),
            'state': args.state,
        }
        write_report(report, ordered, summary)
        print('report: %s' % report)
    if not args.dry_run:
        save_state(Path(args.state), state)
        print('state: %s' % args.state)
    return 1 if violations else 0


if __name__ == '__main__':
    sys.exit(main())
