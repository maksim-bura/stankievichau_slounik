# Dictionary App — Architecture Guide

## Goal
A Belarusian–Russian bilingual dictionary app. Queries in either language search headwords (Belarusian), translations (Russian `<t>` tags), or examples (`<ex>` tags), with tab‑separated search modes and a split‑pane UI.

## Project Layout
```
dictionary_app/
├── app/                  # Qt UI layer
│   ├── main_window.py    # Main window, wiring, orchestration
│   ├── panels/           # Pluggable UI panes
│   │   ├── entry_viewer.py        # Entry display + navigation bar
│   │   ├── search_results_list.py # Headword results list
│   │   ├── sources_panel.py       # Sources panel + SourcesToggle
│   │   └── sources_renderer.py    # Sources XML → HTML rendering
│   ├── widgets/          # Reusable Qt widgets
│   │   ├── dict_text_browser.py   # QTextBrowser with scroll restoration
│   │   ├── icon_button.py         # Flat icon button
│   │   ├── search_box.py          # QLineEdit with keyboard nav signals
│   │   ├── settings_button.py     # Settings gear button + menu
│   │   └── sources_button.py      # Sources toggle button
│   └── shortcuts/
│       └── shortcuts.py  # Global Ctrl+C handler
├── build/                # SQLite database output (gitignored)
│   └── dictionary.db
├── data/
│   ├── dictionary.xml    # Main dictionary entries
│   ├── sources.xml       # Sources/abbreviations reference
│   └── source_mappings.json
├── db/                   # Database layer
│   ├── search_engine.py  # SearchEngine — all query logic
│   └── build_database.py # Build SQLite from XML
├── format/               # Entry formatting pipeline
│   ├── entry_formatter.py  # XML → HTML formatter
│   ├── link_handler.py     # Link creation (<a> tags)
│   └── source_mapper.py    # Abbreviation → source-id mapper
├── localization/
│   ├── __init__.py       # strings object from JSON
│   └── strings.json
├── theme/
│   ├── layout_constants.py  # Pixel/metric constants
│   └── widget_styles.py     # Global + per-widget stylesheets
├── utils/
│   ├── accent_utils.py    # remove_accents, normalize_je, get_text_excluding_src
│   ├── case_utils.py      # compile_search_regex (accent-insensitive, word-boundary-aware)
│   └── scroll_manager.py  # Anchor scroll + restore
├── run.py
└── main.py
```

## Key Design Decisions

### Search Modes
- Three boolean options: `search_in_headwords`, `search_in_translations`, `search_in_examples`
- **Exclusive mode**: exactly one of translations/examples ON, headwords OFF — shows preview snippets in the entry pane, hides the results list
- **Combined mode**: headwords ON + examples ON, translations OFF — headword matches fill the results list, example matches fill previews
- **Any other combination** (or headwords-only) → standard headword search with results list visible
- Empty search results show `"Няма вынiкаў."` in the entry pane; the results list is left empty

### Content Index
- `content_index` table in `dictionary.db`: `(entry_id, tag_type, searchable_text)` + indexes
- Built by `build_database.py` — extracts `<t>`/`<ex>` text at build time with same exclusion rules as the search engine
- Translation/examples search queries the index via `LIKE` first, then fetches only matching entries for preview building — avoids parsing all 30k XML strings per query

### Exclusion Rules
| Context | Excluded elements |
|---|---|
| Translation (`<t>`) search indexing | `<src>`, `<st>`, `<see>`, `<i lang="vl">`, `<i excl="true">` |
| Translation preview highlight | Same as indexing — excluded children rendered but not highlightable |
| Example (`<ex>`) search indexing | `<src>`, `<st>`, `<i lang="ru">` |
| Example preview highlight | Same as indexing |

### Preview System
- Translation previews: sense number (from enclosing `<sense>`) prepended as `<span class="b">`, optional preceding `<ex>—` prepended as `<span class="g">`
- Example previews: trailing `—<t>` appended as `<span class="t">` when pattern detected
- Multiple matching elements with the same headword within one entry are **grouped** into one preview
- Preview spacing: `<br>` between sense previews only when `<br>` exists in the raw XML between matched elements; ` <br><br>` between headword groups
- Preview headwords are clickable links (`preview:{entry_id}|{headword}`) — clicking opens the full entry with search-query highlighting

### Search Regex (`compile_search_regex`)
- Accent-insensitive: every literal character accepts optional combining marks U+0300/U+0301 via `_ACCENT_COMB`
- Wildcards: `*` → one or more word chars, `?` → one word char, stop at whitespace
- Custom word-boundary lookarounds: `(?<![\w\'\u2019\u02BC-])` / `(?![\w\'\u2019\u02BC-])` — treats punctuation as boundaries, apostrophe and hyphen as word chars
- Trailing space in query → exact-word match (adds trailing boundary)
- Multi-word queries: regex `\s+` between word patterns
- `ё`↔`е` mapping (`normalize_je`): applied only for translation search, not for examples

### Entry Formatting
- `entry_formatter._process_element` is recursive: processes children via `LinkHandler` for linkable tags (`src`, `st`, `see`), CSS‑class‑wraps others
- Each child's CSS class is applied by the **parent iteration** (not self-formatting) — no double-wrapping
- `<src>` links get `font-style: normal`; `<st>` links inherit italic
- `LinkHandler.create_link` handles source abbreviation resolution via `SourceMapper`

### Results List (`SearchResultsList`)
- Fixed width (`RESULTS_MIN_WIDTH` = 150px)
- No focus policy on the widget (keyboard nav goes through SearchBox signals)
- Tooltip always shown (displays normalized headword without accents)
- First item auto-selected on `display_results`
- `_widget` is the internal QListWidget; `current_results` is the full result data set

### Highlighting
- Entry opened from preview → search terms highlighted with `#FFF9C4` background
- Same-entry see links preserve highlight (`_highlighted_entry_id` matches); different-entry see links clear it
- Close button on navigation bar → `_dismiss_highlight()` re-renders without highlight
- Highlight applied via `SearchEngine._apply_highlight`: protects `<a>` tags with null-byte placeholders, splits by HTML tags, applies regex highlights to text-only parts

### Navigation Bar
- History stack of visited entries (headword + sense_parts)
- Back/Forward/Close buttons
- Preview state uses sentinel `'__preview__'` as headword — intercepted in `open_entry_by_headword`

## Writing Conventions
- No comments in code unless essential
- Module-level constants, no inline literals (use `theme/layout_constants.py`)
- All CSS in `theme/widget_styles.py` (one source of truth)
- Qt signals for cross-component communication
- Private methods use `_` prefix
- Pane = self-contained UI component (EntryViewer, SourcesPanel, SearchResultsList)
- Window = top-level OS window (MainWindow)
