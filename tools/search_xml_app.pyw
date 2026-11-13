"""Simple window for searching the marked-up XML files.

Open: double-click tools/search_xml_app.pyw
Type a query and press Enter.
"""
import re
import sys
import tkinter as tk
from pathlib import Path
from tkinter import ttk

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import search_xml

WINDOW_TITLE = 'Search XML'
WINDOW_WIDTH = 1100
WINDOW_HEIGHT = 650
SNIPPET_WIDTH = 260
COLUMNS = (
    ('headword', 'Headword', 190),
    ('file', 'File', 280),
    ('line', 'Line', 60),
    ('snippet', 'Snippet', 520),
)


def relative_path(path):
    try:
        return path.resolve().relative_to(
            search_xml.PROJECT_ROOT,
        ).as_posix()
    except ValueError:
        return path.as_posix()


def search_rows(query, use_regex, ignore_case):
    flags = re.IGNORECASE if ignore_case else 0
    pattern = re.compile(query if use_regex else re.escape(query), flags)
    patterns = [search_xml.DEFAULT_GLOB]
    excluded = set(search_xml.DEFAULT_EXCLUDE)
    paths = [str(search_xml.DEFAULT_PATH)]
    rows = []
    files_with_matches = 0
    for path in search_xml.iter_files(paths, patterns, excluded):
        try:
            text = search_xml.read_text(path)
        except (OSError, UnicodeDecodeError):
            continue
        lines = text.splitlines()
        found = search_xml.collect_matches(lines, pattern)
        if not found:
            continue
        files_with_matches += 1
        blocks, headwords = search_xml.scan_blocks(text)
        line_headwords = search_xml.collect_line_headwords(
            text, search_xml.line_starts(text), found, blocks, headwords,
        )
        display = relative_path(path)
        for index in sorted(found):
            column = found[index][0][0] + 1
            rows.append((
                ', '.join(line_headwords.get(index, [])),
                display,
                index + 1,
                search_xml.clip(lines[index], column - 1, SNIPPET_WIDTH),
            ))
    return rows, files_with_matches


class SearchWindow:
    def __init__(self, root):
        self.root = root
        root.title(WINDOW_TITLE)
        root.geometry('%dx%d' % (WINDOW_WIDTH, WINDOW_HEIGHT))
        root.minsize(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2)

        self.query = tk.StringVar()
        self.use_regex = tk.BooleanVar(value=False)
        self.ignore_case = tk.BooleanVar(value=True)
        self.status = tk.StringVar(value='Type a query and press Enter.')

        top = ttk.Frame(root, padding=(8, 8, 8, 4))
        top.pack(fill='x')
        ttk.Label(top, text='Query:').pack(side='left')
        self.entry = ttk.Entry(top, textvariable=self.query)
        self.entry.pack(side='left', fill='x', expand=True, padx=(6, 6))
        self.entry.bind('<Return>', self.run_search)
        ttk.Button(
            top, text='Search', command=self.run_search,
        ).pack(side='left')
        ttk.Checkbutton(
            top, text='Regex', variable=self.use_regex,
        ).pack(side='left', padx=(10, 0))
        ttk.Checkbutton(
            top, text='Ignore case', variable=self.ignore_case,
        ).pack(side='left', padx=(10, 0))

        table = ttk.Frame(root, padding=(8, 0, 8, 4))
        table.pack(fill='both', expand=True)
        self.tree = ttk.Treeview(
            table, columns=[item[0] for item in COLUMNS],
            show='headings', selectmode='browse',
        )
        for key, title, width in COLUMNS:
            self.tree.heading(key, text=title)
            self.tree.column(key, width=width, stretch=(key == 'snippet'))
        vertical = ttk.Scrollbar(
            table, orient='vertical', command=self.tree.yview,
        )
        horizontal = ttk.Scrollbar(
            table, orient='horizontal', command=self.tree.xview,
        )
        self.tree.configure(
            yscrollcommand=vertical.set, xscrollcommand=horizontal.set,
        )
        self.tree.grid(row=0, column=0, sticky='nsew')
        vertical.grid(row=0, column=1, sticky='ns')
        horizontal.grid(row=1, column=0, sticky='ew')
        table.rowconfigure(0, weight=1)
        table.columnconfigure(0, weight=1)

        ttk.Label(
            root, textvariable=self.status, padding=(8, 0, 8, 8),
        ).pack(fill='x')
        self.entry.focus_set()

    def run_search(self, _event=None):
        query = self.query.get()
        if not query:
            self.status.set('Type a query first.')
            return
        try:
            rows, file_count = search_rows(
                query, self.use_regex.get(), self.ignore_case.get(),
            )
        except re.error as exc:
            self.status.set('Invalid regular expression: %s' % exc)
            return
        self.tree.delete(*self.tree.get_children())
        for row in rows:
            self.tree.insert('', 'end', values=row)
        self.status.set(
            '%d match(es) in %d file(s)' % (len(rows), file_count),
        )


def main():
    root = tk.Tk()
    SearchWindow(root)
    root.mainloop()


if __name__ == '__main__':
    main()
