import sys
import xml.etree.ElementTree as ElementTree
from pathlib import Path

from digraph_export import write_workbook

TOOLS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = TOOLS_DIR.parent

sys.path.insert(0, str(PROJECT_ROOT))

from dictionary_app.db.build_database import get_source_names, get_source_path
from dictionary_app.utils.xml_schema import ATTR_EXCL, ATTR_HW

DEFAULT_OUTPUT = 'see_hw_links.xlsx'
HEADERS = ('Загаловак артыкула', 'Спасылка <see>')
COLUMN_WIDTHS = (34, 95)
SHEET_TITLE = 'Спасылкі з hw'


def _main_headword(entry):
    fallback = ''
    for headword in entry.iter('hw'):
        text = ''.join(headword.itertext()).strip()
        if not text:
            continue
        if not fallback:
            fallback = text
        if headword.get(ATTR_EXCL) is None:
            return text
    return fallback


def see_hw_rows():
    rows = []
    for source_file in get_source_names():
        root = ElementTree.parse(get_source_path(source_file)).getroot()
        for entry in root.iter('entry'):
            headword = _main_headword(entry)
            for see in entry.iter('see'):
                if see.get(ATTR_HW) is None:
                    continue
                rows.append((
                    headword,
                    ElementTree.tostring(see, encoding='unicode').strip(),
                ))
    return rows


def main(argv):
    rows = see_hw_rows()
    output = argv[1] if len(argv) > 1 else DEFAULT_OUTPUT
    path = write_workbook(
        rows, output, headers=HEADERS, column_widths=COLUMN_WIDTHS,
        sheet_title=SHEET_TITLE,
    )
    print(f'{len(rows)} see link(s) written to {path}')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
