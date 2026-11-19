import re

from dictionary_app.utils.xml_schema import ATTR_EXCL, ATTR_ID


HW_ATTRS_TEXT_RE = re.compile(r'<hw\b([^>]*)>(.*?)</hw>', re.DOTALL)
HW_TEXT_RE = re.compile(r'<hw\b[^>]*>(.*?)</hw>', re.DOTALL)
ATTR_ID_RE = re.compile(r'\bid\s*=\s*"([^"]*)"')
ENTRY_ID_RE = re.compile(r'<entry\b[^>]*\b' + ATTR_ID + r'="([^"]*)"')
EXCL_ATTR_RE = re.compile(r'\b' + ATTR_EXCL + r'\s*=')
