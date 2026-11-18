"""Compare the raw OCR files with the marked-up XML, per letter.

Run: py -3 tools/compare_raw_markup.py --coverage
     py -3 tools/compare_raw_markup.py --conventions
     py -3 tools/compare_raw_markup.py --coverage --letter Cz --limit 0

Read-only. Prints compact ASCII-labelled summaries: how much of each raw file
is already covered by the XML (aligned in print order), which raw blocks have no
XML entry, which XML entries have no raw counterpart, and the markup
conventions in use per file (accent marks per tag, split source runs, break
forms, attributes). Cyrillic appears only in samples, never in labels.

Exit 0 when the report ran, 1 when a paired file is missing or unreadable.
"""
import argparse
import difflib
import re
import sys
import xml.etree.ElementTree as ElementTree
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DICTIONARY_DIR = PROJECT_ROOT / 'dictionary_app' / 'data' / 'dictionary'
RAW_DIR = PROJECT_ROOT / 'markup_app' / 'data' / 'dictionary_raw'
XML_SUFFIX = '.xml'
RAW_SUFFIX = '_raw.txt'
BULLET = '\u2022'
ACUTE = '\u0301'
GRAVE = '\u0300'
ACCENTS = str.maketrans('', '', ACUTE + GRAVE)
WORD = re.compile(r'[^\W_]+', re.UNICODE)
SPLIT_SOURCE = re.compile(r'</src>\s*[;,]\s*<src>')
SPACED_BREAK = '<br />'
PAIRED_BREAK = '<br></br>'
ASCII_APOSTROPHE = "'"
CURLY_APOSTROPHES = '\u2019\u02bc'
MATCH_CHARS = 200
LOOKAHEAD = 5
MATCH_THRESHOLD = 0.55
SAMPLE_WIDTH = 60
ORDER_KEY = 6
ACCENT_TAGS = ('hw', 'g')


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', default=str(PROJECT_ROOT))
    parser.add_argument('--letter', default='')
    parser.add_argument('--limit', type=int, default=10)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--coverage', action='store_true')
    group.add_argument('--conventions', action='store_true')
    return parser.parse_args()


def limit_of(value):
    return None if value <= 0 else value


def discover_pairs(root):
    dictionary_dir = root / DICTIONARY_DIR.relative_to(PROJECT_ROOT)
    raw_dir = root / RAW_DIR.relative_to(PROJECT_ROOT)
    xml_files = {path.stem.replace('dictionary_', ''): path
                 for path in sorted(dictionary_dir.glob('*' + XML_SUFFIX))}
    raw_files = {path.name[len('dictionary_'):-len(RAW_SUFFIX)]: path
                 for path in sorted(raw_dir.glob('*' + RAW_SUFFIX))}
    names = sorted(set(xml_files) | set(raw_files))
    return [(name, xml_files.get(name), raw_files.get(name)) for name in names]


def read_text(path):
    return path.read_text(encoding='utf-8-sig')


def normalize(text):
    return ' '.join(WORD.findall(text.translate(ACCENTS).lower()))


def similarity(left, right):
    return difflib.SequenceMatcher(
        None, left[:MATCH_CHARS], right[:MATCH_CHARS], autojunk=False).ratio()


def clip(text, width=SAMPLE_WIDTH):
    flat = ' '.join(text.split())
    return flat if len(flat) <= width else flat[:width] + '...'


def main_headword(entry):
    for element in entry.iter('hw'):
        if 'excl' not in element.attrib:
            return ''.join(element.itertext()).strip()
    return ''


def load_entries(xml_path):
    root = ElementTree.parse(xml_path).getroot()
    entries = []
    for entry in root.iter('entry'):
        text = ' '.join(''.join(entry.itertext()).split()).replace(BULLET, '')
        entries.append({'headword': main_headword(entry), 'text': normalize(text)})
    return entries


def read_raw_blocks(raw_path):
    text = read_text(raw_path)
    starts = [index for index, char in enumerate(text) if char == BULLET]
    blocks = []
    for position, start in enumerate(starts):
        end = starts[position + 1] if position + 1 < len(starts) else len(text)
        body = text[start:end].strip()
        blocks.append({'preview': clip(body.replace(BULLET, '', 1)),
                       'text': normalize(body.replace(BULLET, '', 1))})
    return blocks


def align_entries(entries, blocks):
    matches = []
    skipped = []
    position = 0
    for index, entry in enumerate(entries):
        best_score = 0.0
        best_block = None
        for offset in range(LOOKAHEAD):
            candidate = position + offset
            if candidate >= len(blocks):
                break
            score = similarity(entry['text'], blocks[candidate]['text'])
            if score > best_score:
                best_score = score
                best_block = candidate
        if best_block is None or best_score < MATCH_THRESHOLD:
            matches.append((index, None, best_score))
            continue
        skipped.extend(range(position, best_block))
        matches.append((index, best_block, best_score))
        position = best_block + 1
    return matches, skipped, position


def order_hint(entry, blocks, skipped):
    key = entry['text'][:ORDER_KEY]
    for index in skipped:
        if blocks[index]['text'][:ORDER_KEY] == key:
            return index
    return None


def report_coverage(pairs, args):
    failures = 0
    limit = limit_of(args.limit)
    for name, xml_path, raw_path in pairs:
        if xml_path is None or raw_path is None:
            missing = 'XML' if xml_path is None else 'raw'
            print('%s: no %s file, skipped' % (name, missing))
            failures += 1
            continue
        try:
            entries = load_entries(xml_path)
            blocks = read_raw_blocks(raw_path)
        except (OSError, UnicodeDecodeError, ElementTree.ParseError) as exc:
            print('%s: READ %s' % (name, exc))
            failures += 1
            continue
        matches, skipped, consumed = align_entries(entries, blocks)
        aligned = [item for item in matches if item[1] is not None]
        unmatched = [item for item in matches if item[1] is None]
        remaining = len(blocks) - consumed
        last = blocks[consumed - 1]['preview'] if consumed else '-'
        print('%-4s raw=%-5d xml=%-5d aligned=%-5d consumed=%-5d '
              'skipped=%-3d remaining=%-4d last="%s"' % (
                  name, len(blocks), len(entries), len(aligned), consumed,
                  len(skipped), remaining, last))
        shown = 0
        for index, _block, score in unmatched:
            if limit is not None and shown >= limit:
                print('  unmatched xml: +%d more' % (len(unmatched) - shown))
                break
            shown += 1
            hint = order_hint(entries[index], blocks, skipped)
            print('  unmatched xml: #%d "%s" (best %.2f)%s' % (
                index, entries[index]['headword'], score,
                '' if hint is None else ' order-hint=R%03d' % hint))
        shown = 0
        for index in skipped:
            if limit is not None and shown >= limit:
                print('  skipped raw: +%d more' % (len(skipped) - shown))
                break
            shown += 1
            print('  skipped raw: #%d "%s"' % (index, blocks[index]['preview']))
    return 1 if failures else 0


def accent_counts(element):
    text = ''.join(element.itertext())
    return text.count(ACUTE), text.count(GRAVE)


def attribute_combo(element):
    return '+'.join(sorted(element.attrib)) or '-'


def report_conventions(pairs, args):
    failures = 0
    limit = limit_of(args.limit)
    header = ('%-4s %-7s %-13s %-13s %-9s %-6s %-7s %-5s %-14s %-6s %-7s %s' % (
        'file', 'entries', 'hw:a/g', 'g:a/g', 'split-src', 'br', 'br-pair',
        'syn', 'see', 'lang', 'p', 'apos:a/c'))
    print(header)
    for name, xml_path, _raw_path in pairs:
        if xml_path is None:
            print('%-4s no XML file, skipped' % name)
            failures += 1
            continue
        try:
            text = read_text(xml_path)
            root = ElementTree.parse(xml_path).getroot()
        except (OSError, UnicodeDecodeError, ElementTree.ParseError) as exc:
            print('%s: READ %s' % (name, exc))
            failures += 1
            continue
        entries = list(root.iter('entry'))
        accents = {}
        for tag in ACCENT_TAGS:
            acute = grave = 0
            for element in root.iter(tag):
                tag_acute, tag_grave = accent_counts(element)
                acute += tag_acute
                grave += tag_grave
            accents[tag] = (acute, grave)
        sees = Counter(attribute_combo(element) for element in root.iter('see'))
        langs = Counter(element.attrib.get('code', '-')
                        for element in root.iter('lang'))
        see_label = ', '.join('%s=%d' % item for item in sees.most_common(limit))
        lang_label = ', '.join('%s=%d' % item for item in langs.most_common(limit))
        print('%-4s %-7d %-13s %-13s %-9d %-6d %-7d %-5d %-14s %-6s %-7d %d/%d' % (
            name, len(entries),
            '%d/%d' % accents['hw'], '%d/%d' % accents['g'],
            len(SPLIT_SOURCE.findall(text)),
            text.count(SPACED_BREAK), text.count(PAIRED_BREAK),
            text.count('syn="true"'),
            see_label, lang_label,
            len(list(root.iter('p'))),
            text.count(ASCII_APOSTROPHE),
            sum(text.count(char) for char in CURLY_APOSTROPHES)))
    return 1 if failures else 0


def main():
    args = parse_args()
    root = Path(args.root).resolve()
    pairs = discover_pairs(root)
    if args.letter:
        pairs = [item for item in pairs if item[0] == args.letter]
    if not pairs:
        print('no raw/XML pairs found under %s' % root)
        return 1
    if args.coverage:
        return report_coverage(pairs, args)
    return report_conventions(pairs, args)


if __name__ == '__main__':
    sys.exit(main())
