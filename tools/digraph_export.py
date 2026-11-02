import sys
import xml.etree.ElementTree as ElementTree
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font
from openpyxl.utils import get_column_letter

TOOLS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = TOOLS_DIR.parent

sys.path.insert(0, str(PROJECT_ROOT))

from dictionary_app.db.build_database import get_source_names, get_source_path
from dictionary_app.utils.constants import SEP_SORT_SENTINEL
from dictionary_app.utils.extract_content_text import hw_text_excluding_n
from dictionary_app.utils.xml_schema import ATTR_ID

HEADERS = ('Файл', 'Артыкул', 'Загаловак', 'XML загалоўка', 'XML артыкула')
COLUMN_WIDTHS = (18, 22, 32, 44, 90)
SHEET_TITLE = 'Загалоўкі'
SEP_TEXT = '<sep />'


def _has_digraph(text):
    lowered = text.lower()
    return 'дз' in lowered or 'дж' in lowered


def _has_separated_digraph(text):
    lowered = text.lower()
    for index in range(len(lowered) - 2):
        if (lowered[index] == 'д'
                and lowered[index + 1] == SEP_SORT_SENTINEL
                and lowered[index + 2] in 'зж'):
            return True
    return False


def _collect(matches):
    rows = []
    for source_file in get_source_names():
        root = ElementTree.parse(get_source_path(source_file)).getroot()
        for entry in root.iter('entry'):
            entry_xml = ElementTree.tostring(entry, encoding='unicode')
            entry_id = entry.get(ATTR_ID) or ''
            for headword in entry.iter('hw'):
                text = hw_text_excluding_n(headword, SEP_SORT_SENTINEL).strip()
                if not matches(text):
                    continue
                headword_xml = ElementTree.tostring(headword, encoding='unicode')
                rows.append((
                    source_file,
                    entry_id,
                    text.replace(SEP_SORT_SENTINEL, SEP_TEXT),
                    headword_xml.strip(),
                    entry_xml.strip(),
                ))
    return rows


def digraph_rows():
    return _collect(_has_digraph)


def separated_digraph_rows():
    return _collect(_has_separated_digraph)


def write_workbook(rows, output_name, headers=HEADERS,
                   column_widths=COLUMN_WIDTHS, sheet_title=SHEET_TITLE):
    path = Path(output_name)
    if not path.is_absolute():
        path = TOOLS_DIR / path
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = sheet_title
    sheet.append(list(headers))
    for cell in sheet[1]:
        cell.font = Font(bold=True)
        cell.alignment = Alignment(vertical='top', wrap_text=True)
    for row in rows:
        sheet.append(list(row))
    for row in sheet.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = Alignment(vertical='top', wrap_text=True)
    for index, width in enumerate(column_widths, start=1):
        sheet.column_dimensions[get_column_letter(index)].width = width
    sheet.freeze_panes = 'A2'
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(path)
    return path
