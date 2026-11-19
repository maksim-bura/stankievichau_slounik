import re

from dictionary_app.utils.normalize_headword import has_keep_acc, resolve_headword
from markup_app.services.link_text import normalize_headword, strip_tags
from markup_app.utils.xml_patterns import ENTRY_ID_RE, HW_ATTRS_TEXT_RE


_ENTRY_BLOCK_RE = re.compile(r'<entry\b.*?</entry>', re.DOTALL)


def find_entry_blocks(content):
    return _ENTRY_BLOCK_RE.findall(content)


def remove_entry_block(content, block):
    index = content.find(block)
    if index < 0:
        return None
    end = index + len(block)
    if content.startswith('\n\n', end):
        end += 2
    elif content.startswith('\r\n\r\n', end):
        end += 4
    elif index >= 2 and content[index - 2:index] == '\n\n':
        index -= 2
    elif index >= 4 and content[index - 4:index] == '\r\n\r\n':
        index -= 4
    return content[:index] + content[end:]


def block_raw_id(block):
    match = ENTRY_ID_RE.search(block)
    return match.group(1) if match else None


def block_link(block):
    raw = block_raw_id(block)
    if not raw:
        return None
    return normalize_headword(raw)


def block_headwords(block):
    norms = []
    for match in HW_ATTRS_TEXT_RE.finditer(block):
        norms.append(resolve_headword(
            strip_tags(match.group(2)).strip(), has_keep_acc(match.group(1))
        ))
    return norms


def block_matches(block, target_norm):
    return target_norm in block_headwords(block)
