# Dictionary App — Architecture Guide

## Goal
A Belarusian–Russian bilingual dictionary app. Queries in either language search headwords (Belarusian), translations (Russian `<t>` tags), or examples (`<ex>` tags), with tab‑separated search modes and a split‑pane UI.

A separate **markup app** (`AGENTS_markup.md`) provides an entry editor that saves changes back to the source XML files.

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
│   ├── dictionary.db
│   └── markup_checked.json  # Markup app checked states
├── data/
│   ├── dictionary/       # Split XML/TXT files (dictionary_A.xml … dictionary_Z.txt)
│   ├── sources.xml       # Sources/abbreviations reference
│   └── source_mappings.json
├── db/                   # Database layer
│   ├── search_engine.py  # SearchEngine — all query logic
│   └── build_database.py # Build SQLite from XML (reads data/dictionary/ split files)
├── format/               # Entry formatting pipeline
│   ├── entry_formatter.py  # XML → HTML formatter
│   ├── link_handler.py     # Link creation (<a> tags)
│   └── source_mapper.py    # Abbreviation → source-id mapper
├── localization/
│   ├── __init__.py       # strings object from JSON
│   └── strings.json
├── markup/               # Markup app (see AGENTS_markup.md)
│   ├── __init__.py
│   ├── main.py           # Markup app entry point
│   ├── main_window.py    # Markup main window, search, save
│   ├── editor.py         # Text/Author editor, tag buttons, Backspace logic
│   ├── checked_state.py  # Per-entry checked persistence
│   └── styles.py         # Markup-specific styles
├── theme/
│   ├── layout_constants.py  # Pixel/metric constants
│   └── widget_styles.py     # Global + per-widget stylesheets
├── utils/
│   ├── accent_utils.py    # remove_accents, normalize_je, get_text_excluding_src
│   ├── case_utils.py      # compile_search_regex (accent-insensitive, word-boundary-aware)
│   └── scroll_manager.py  # Anchor scroll + restore
├── AGENTS.md             # This file (dictionary app guide)
├── AGENTS_markup.md      # Markup app guide
├── run.py                # Dictionary app launcher
├── run_markup.py         # Markup app launcher
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

### Search Ranking
Translation and example preview results are sorted by a computed rank tuple `(rank, word_pos, word_len)`:

| Rank | Match type | Source |
|---|---|---|
| 1 | Exact word | `<t lvl="1">` or `<tp lvl="1">` |
| 2 | Portion of phrase | `<t lvl="1">` or `<tp lvl="1">` |
| 3 | Exact word | `<t lvl="2">` or `<tp lvl="2">` |
| 4 | Portion of phrase | `<t lvl="2">` or `<tp lvl="2">` |
| 5 | Exact word | `<t lvl="3">` or `<tp lvl="3">` |
| 6 | Portion of phrase | `<t lvl="3">` or `<tp lvl="3">` |
| 7 | No `lvl` / `<ex>` match | — |

- Both `<t>` (direct `lvl` attribute) and `<tp>` (child element with `lvl`) are evaluated; `min()` picks the best rank
- `<tp>` defaults to `lvl="1"` when `lvl` is absent
- Portions sort: primary by word position in the text (earlier wins), secondary by word length (shorter wins)
- All other preview metadata (sense numbers, grouping, spacing) is identical; ranking only controls sort order

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

### Window Layout (`MainWindow.setup_ui`)
- Vertical main layout: top row (search box + sources button + settings button), bottom row (results list + splitter)
- Bottom row is `QHBoxLayout` (not a splitter): results list at stretch 0 (fixed 150px) + `bottom_splitter` at stretch 1
- `bottom_splitter` (`QSplitter` Horizontal) holds: entry viewer (initial `SPLITTER_ENTRY_INITIAL`=400px) + sources viewer (initial `SPLITTER_SOURCES_INITIAL`=400px)
- Both splitter panes are non-collapsible (`setCollapsible(0/1, False)`)
- Window default: 765x650px, minimum width dynamically computed as sum of visible panel minimums
- `_update_min_width()` recalculates on every show/hide of results list or sources panel
- Global stylesheet applied via `QApplication.instance().setStyleSheet(GLOBAL_STYLE)`

### Entry Viewer (`EntryViewer`)
- `DictTextBrowser` (QTextBrowser subclass) inside a QVBoxLayout with `NavigationBar` above it
- Read-only, no external links (`setOpenExternalLinks(False)`), `ClickFocus` policy
- Document margin: 15px left/right (`DOCUMENT_MARGIN`) via `rootFrame().frameFormat()`
- `ENTRY_STYLESHEET` set as document default stylesheet for HTML rendering
- `stored_html` holds the last displayed HTML for refresh/restore
- `ScrollManager` handles anchor scroll, resize re-scroll, and cached state restore
- `setSource` overridden to block navigation for `word:`, `source:`, `preview:` schemes

### Navigation Bar (`NavigationBar`)
- Fixed height 30px (`BAR_HEIGHT`), horizontal layout: Back | Back-spacer | Flex-spacer | Forward | stretch | Close
- Back/Forward buttons: 95px wide each (`NAV_BUTTON_WIDTH`), emoji labels, flat transparent style
- Close button: `IconButton`, 30x30px (`BUTTON_SIZE`)
- Visible only when `navigation_stack` has >1 entry
- Back button hidden when at index 0 (replaced by fixed-width invisible spacer to keep layout stable)
- History stack of `{headword, sense_parts}` dicts; `push()` truncates forward history on new push
- Sentinel `'__preview__'` as headword -- intercepted in `open_entry_by_headword` to restore preview

### Results List (`SearchResultsList`)
- Fixed width (`RESULTS_MIN_WIDTH` = 150px), horizontal scrollbar always off
- No focus policy on the QListWidget -- keyboard nav (Up/Down/Enter) routed via `SearchBox` signals
- Custom `_ElidingDelegate`: elides text exceeding `viewport().width() - 10`px using `Qt.ElideRight`
- Tooltip shown only for items that overflow (text wider than viewport)
- Tooltip text = `remove_accents(raw_headword)` -- accent-stripped headword
- Font: Cambria/Times New Roman serif, 12pt bold (via `GLOBAL_STYLE`)
- Item CSS: left border 3px solid transparent (idle), grey on hover (`#c0c0c0`), blue on selected (`#7c9ec0`); background white -> `#fafafa` hover -> `#edf7fd` selected; text always black
- Items carry `UserRole` = entry_link, `UserRole+1` = raw headword
- First item auto-selected after `display_results`
- `display_results()` also clears entry viewer and scroll cache

### Search Box (`SearchBox`)
- `QLineEdit` subclass, fixed height 30px (`SEARCH_BOX_HEIGHT`)
- Signals: `navigate_up` (Up arrow), `navigate_down` (Down arrow), `activate` (Enter/Return)
- Style: white bg, 1px `#c0c0c0` border, 3px radius, 2px padding

### Settings Button (`SettingsButton`)
- Emoji gear icon, 30x30px (`BUTTON_SIZE`), opens `QMenu` on click
- Menu structure: heading -> separator -> Radio1 "Belarusian" (with sub-options) -> Radio2 "Russian"
- Radio buttons use colored circles (green checked / white unchecked)
- Sub-options use checkmarks (checked/unchecked), indented 24px left margin
- Sub-options: at least one must remain checked (`_sync_sub_options` disables the last checked one)
- `get_option_states()` returns the three boolean search options dict
- When radio2 (Russian) is checked: headwords=False, translations=True, examples=False
- When radio1 (Belarusian) is checked: headwords/examples/translations from sub-option checkboxes

### Sources Panel (`SourcesPanel`)
- `DictTextBrowser` (read-only) + search `QLineEdit` + close button in a VBox layout
- Toggle button (`SourcesButton`): book emoji, 30x30px, `MENU_BUTTON_STYLE`
- Loaded from `data/sources.xml` via `SourcesRenderer` (XML to HTML)
- Search box filters source entries by text match
- Panel shown/hidden via toggle button; visibility tracked in `sources_panel_visible`

### Scroll Manager (`ScrollManager`)
- `scroll_to_anchor(anchor)`: sets HTML `#anchor`, timers for scroll (100ms) and resize re-scroll (150ms)
- `cache_state()` / `restore_state()`: save/restore scroll position across refreshes
- `save_scroll()` / `restore_content()`: debounce content changes, restore scroll after 50ms delay
- `handle_resize()`: re-scrolls to anchor after 150ms debounce

### Highlighting
- Entry opened from preview -> search terms highlighted with `#FFF9C4` background
- Same-entry see links preserve highlight (`_highlighted_entry_id` matches); different-entry see links clear it
- Close button on navigation bar -> `_dismiss_highlight()` re-renders without highlight
- Highlight applied via `SearchEngine._apply_highlight`: concatenates all text parts, applies `finditer` across the full text, maps highlights back to individual parts

### Global Shortcut
- Ctrl+C copies selection from any QTextEdit via `install_global_copy` in `app/shortcuts/shortcuts.py`

## Writing Conventions
- No comments in code unless essential
- Module-level constants, no inline literals (use `theme/layout_constants.py`)
- All CSS in `theme/widget_styles.py` (one source of truth)
- Qt signals for cross-component communication
- Private methods use `_` prefix
- Pane = self-contained UI component (EntryViewer, SourcesPanel, SearchResultsList)
- Window = top-level OS window (MainWindow)

## Database Schema
- `dictionary` table: `(id INTEGER PRIMARY KEY, headword, normalized_headword, full_entry, entry_link, source_file)`
- `sub_headwords` table: `(id, headword, normalized_headword, main_entry_id)` — sub-headwords share parent entry
- `content_index` table: `(entry_id, tag_type, searchable_text)` — pre-built index for translation/examples search
- `source_file` column tracks which file in `data/dictionary/` each entry came from (used by markup app for save)
