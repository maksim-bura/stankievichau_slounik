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
│   │   ├── sources_panel.py       # Sources panel (viewer + search + magnifier button)
│   │   ├── sources_renderer.py    # Sources XML → HTML (build_filtered_html)
│   │   └── sources_toggle.py      # Splitter resizing helpers when toggling sources
│   ├── widgets/          # Reusable Qt widgets
│   │   ├── dict_text_browser.py   # QTextBrowser: block word/source/preview routes, keep margins
│   │   ├── icon_button.py         # Flat icon button
│   │   ├── search_box.py          # QLineEdit with keyboard nav signals
│   │   ├── settings_button.py     # Settings gear button + menu (search-mode options)
│   │   ├── sources_button.py      # Sources toggle button
│   │   └── result_list_helpers.py # ElidingDelegate, select_row, navigate_rows
│   └── shortcuts/
│       └── shortcuts.py  # Global Ctrl+C handler
├── build/                # SQLite database output (gitignored)
│   ├── dictionary.db
│   └── markup_checked.json  # Markup app checked states
├── data/
│   ├── dictionary/       # Split XML entry files (dictionary_A.xml …); raw OCR text in raw_data/
│   ├── sources.xml       # Sources/abbreviations reference
│   └── source_mappings.json
├── db/                   # Database layer
│   ├── search_engine.py  # SearchEngine — all query logic
│   ├── build_database.py # Build SQLite from XML (reads .xml files in data/dictionary/)
│   └── bootstrap.py      # create_search_engine(): rebuild-if-stale, then open
├── format/               # Entry formatting pipeline
│   ├── entry_formatter.py  # XML → HTML formatter
│   ├── link_handler.py     # Link creation (<a> tags) + URL routing
│   └── source_mapper.py    # Abbreviation → source-id mapper
├── localization/
│   ├── loader.py         # strings object from JSON
│   └── strings.json
├── markup/               # Markup app (see AGENTS_markup.md)
├── theme/
│   ├── layout_constants.py  # Pixel/metric constants
│   └── widget_styles.py     # Global + per-widget stylesheets, named palette + RESULTS_LIST_STYLE
├── utils/
│   ├── constants.py      # Glyphs (arrows, check/radio, gear, magnifier, books, floppy), scheme names,
│   │                     #   triangle entities — single source
│   ├── text_utils.py     # remove_accents, normalize_jo, alphabet_sort_key
│   ├── search_regex.py   # compile_search_regex (accent-insensitive, word-boundary-aware)
│   ├── scroll_manager.py # Anchor scroll + cached state restore
│   └── content_rules.py  # get_text_excluding_src, content_text, index_text, hw_text_excluding_n, d_hw_variants
├── AGENTS.md             # This file (dictionary app guide)
├── AGENTS_markup.md      # Markup app guide
├── run.py                # Dictionary app launcher
└── run_markup.py         # Markup app launcher
```

## Key Design Decisions

### Search Modes
- Three boolean options: `search_in_headwords`, `search_in_translations`, `search_in_examples`
- **Exclusive mode**: exactly one of translations/examples ON, headwords OFF — shows preview snippets in the entry pane, hides the results list
- **Combined mode**: headwords ON + examples ON, translations OFF — headword matches fill the results list, example matches fill previews
- **Any other combination** (or headwords-only) → standard headword search with results list visible
- Empty main-search results leave the entry pane empty (the results list is cleared). The "no results" message (`strings.no_results`, "Няма вынікаў.") is used ONLY by `sources_renderer.build_filtered_html` when a sources search matches no section.
- **Settings state machine** (`SettingsButton.get_option_states`): `_russian_radio` → `{headwords:False, translations:True, examples:False}`; `_belarusian_radio` → `{headwords:_headwords_option(), translations:False, examples:_examples_option()}` — translations is ALWAYS False for Belarusian. Sub-options (Belarusian) control headwords + examples only.
- **Combined mode does a dual search**: `on_search` runs TWO separate `search_engine.search()` calls (headwords-only fills the list, examples-only fills previews). This keeps the results list showing only headword matches. Do NOT collapse this into a single call.

### Content Index
- `content_index` table in `dictionary.db`: `(entry_id, tag_type, searchable_text)` + indexes
- Built by `build_database.py` — extracts `<t>`/`<ex>` text at build time with same exclusion rules as the search engine
- Translation/examples search queries the index via `LIKE` first, then fetches only matching entries for preview building — avoids parsing all 30k XML strings per query
- `SearchEngine.get_parsed_entry(entry_id, xml_string)` parses an entry XML once and caches the root in `_parsed_cache` keyed by `entry_id`. It is reused wherever entry roots are needed (`_annotate_content_matches`, `get_main_headword`, preview-link clicks) so the same entry is never re-parsed per action.
- `SearchEngine.get_main_headword(entry_id, xml_string)` returns the first `<hw>`'s full text (`''.join(element.itertext()).strip()`), including any embedded `<n>` — the canonical main-headword text for arrow decisions.

### Exclusion Rules
| Context | Excluded elements |
|---|---|
| Translation (`<t>`) search indexing | `<src>`, `<st>`, `<see>`, `<i lang="vl">`, `<i excl="true">` |
| Translation preview highlight | Same as indexing — excluded children rendered but not highlightable |
| Example (`<ex>`) search indexing | `<src>`, `<st>`, `<i lang="ru">` |
| Example preview highlight | Same as indexing |

### Search Ranking
Translation and example preview results are classified into three tiers (active when `lvl="1"` markup is present) and sorted within each alphabetically:

| Tier | Match type |
|---|---|
| 0 | Exact match within `lvl="1"` content — the query spans the entire text of a `<t lvl="1">` / `<tp lvl="1">` |
| 1 | Partial match within `lvl="1"` content — the query is a substring of such text |
| 2 | Match outside `lvl="1"` content (bare `<t>`/`<ex>`, or `lvl` 2/3 elements) |

- Rank is computed per matched element as the `min` tier across the element's own text and any nested `<tp>` child's text (`_tier_for_match`): a `lvl="1"` element yields `0` for a full-span match and `1` for a substring; any other level or no `lvl` attribute yields `2`.
- Within a tier, preview groups sort alphabetically by preview headword using `alphabet_sort_key` (Belarusian alphabet order, `ґ` after `г` before `д`).
- The current source data carries no `lvl` attributes (see Source Data State), so every match lands in tier 2 — all alphabetical, no exact/portion split until `lvl` markup is re-introduced.
- All other preview metadata (sense numbers, grouping, spacing) is identical; ranking only controls sort order.

### Source Data State (`<tp>` / `lvl`)
- All `data/dictionary/dictionary_*.xml` source files are stripped of every `<tp>` tag and `lvl` attribute — inner text is kept, only bare `<t>` tags remain. This is a **data-only** change.
- ґ-initial entries live in `data/dictionary/dictionary_G.xml` (untracked; the tracked `data/dictionary/dictionary_*.xml` set does not include G). The authoritative OCR text is `data/dictionary/raw_data/dictionary_G_raw.txt` (also untracked) — when editing or reconstructing G entries, verify against the raw lines. Since `dictionary_G.xml` is untracked, remember it is NOT part of `git status`; rebuilds/saves still target the file via `get_source_path`.
- `dictionary_G.xml` is kept in the raw file's print order (anchored to `dictionary_G_raw.txt`). The on-screen list order is alphabetical regardless of file order because search results are sorted by `alphabet_sort_key` (see Collation Rules) — so file order and list order are intentionally different. All other letter files are also in print order; none should be re-sorted alphabetically in the files.
- Code support for `<tp>`/`lvl` is retained even though the data no longer uses it: `_compute_t_match_rank` still computes the three ranking tiers (see Search Ranking), `entry_formatter` still maps the `tp` CSS class, and the markup editor still offers `tp` and `lvl="1"` buttons (see AGENTS_markup.md → Tag Buttons). These paths are dormant until `<tp>`/`lvl` markup is re-introduced into the data.

### Preview System
- Translation previews: sense number prepended as `<span class="{num_tag}">` — `num_tag` is the sense's `<n>` element when present (falling back to `<b>`); **unless** the matched `<t>` belongs to a sub-headword `<d>` nested inside the sense (walk from the `<t>` to the `<sense>` crossing a `<d>`), in which case NO sense number is prepended — a sub-headword (e.g. `ґарба́рны промысл`) is its own entry and must not carry the enclosing main sense's number. When a matched `<t>` is directly preceded by an `<ex>` with `—` tail, the whole `<ex>—<t>` block is emitted as `<span class="g">…</span>—` + the `<t>` preview; **if the `<ex>` is itself preceded by a `<t>`** (the `t . ex — t` chain), that preceding `<t>` is included as leading context too (`<span class="t">…</span>` + its tail), mirroring the embedded-t-in-ex path (the «щи»/гарох pattern). No context is taken from siblings further back (this avoids leaking unrelated elements like a headword separator `<b>:</b>` into the preview).
- **Absorbed-`<t>` suppression (translation only):** when a matched `<t>` is immediately followed by an `<ex>` (with `—` tail) whose next sibling is another matched `<t>`, the earlier `<t>` becomes the leading context of the later one and is NOT emitted as its own standalone preview — this avoids duplicating it (e.g. `в лицо` matched twice shows as one `в лицо. У вабліччу… —в лицо мне…` preview).
- Example previews: trailing `—<t>` appended as `<span class="t">` when pattern detected
- Multiple matching elements with the same headword within one entry are **grouped** into one preview
- Results are deduplicated by `entry_id`; a deduped row attaches **all** of the entry's matches as previews (across every sub-headword) — the surviving headword is NOT used to filter the preview list
- Preview spacing: `<br>` between sense previews only when `<br>` exists in the raw XML between matched elements; ` <br><br>` between headword groups
- Preview headwords are clickable links (`preview:{entry_id}|{headword}`) — clicking opens the full entry with search-query highlighting
- **Preview headword aggregation (`_preview_hw_fields`):** a matched element inside a `<d>` → its ancestor `<d>`'s direct `<hw>` children joined with `|` (plus the n-stripped sort variant); otherwise the entry's `<hw>`s that sit **outside any sense OR inside the same sense as the match** (via `_enclosing_sense`) are joined with `|` (entry with no `<d>`), or the first of those taken (entry that has `<d>`s elsewhere but whose match is outside one) — secondary headwords living in OTHER senses (e.g. `ґатунак воўны` for a sense-1 match) are NOT appended. Fallback to the caller's headword if nothing qualifies. The results list renders `|` as `, ` and scrolls to the first headword. Works for any number of `<hw>`s in both the d-ful and d-less cases.

### Search Regex (`compile_search_regex`)
- Accent-insensitive: every literal character accepts optional combining marks U+0300/U+0301 via `_ACCENT_COMB`
- Wildcards: `*` → one or more word chars, `?` → one word char, stop at whitespace
- Custom word-boundary lookarounds: `(?<![\w\'\u2019\u02BC-])` / `(?![\w\'\u2019\u02BC-])` — treats punctuation as boundaries, apostrophe and hyphen as word chars
- Trailing space in query → exact-word match (adds trailing boundary)
- Multi-word queries: regex `\s+` between word patterns
- `ё`↔`е` mapping (`normalize_jo`) — see Accent-Handling Chain for where it applies

### Accent-Handling Chain
`remove_accents` is applied at EVERY layer: SQL `normalized_headword` at build time, query normalization, result-list item display text, entry-link matching, and preview headwords. Never drop an accent-strip step on one layer only — it must stay consistent across build, search, and display.
- `normalize_jo` (`ё`→`е`, `Ё`→`Е`) in `utils/text_utils.py` is applied **only** for translation search (`tag='t'`), never for examples.
- In `MainWindow.on_search`: `_search_normalize` is set True only when translations-only (translations ON and examples OFF); `_search_in_headwords` mirrors the option. These flags steer which classes get highlighted (see Highlighting).

### Wildcard / LIKE building
- Headword search builds a SQL `LIKE` pattern from the query: `?` → `_`, `*` → `%`, then wraps with `%`, then re-filters results by the compiled regex on accent-stripped text (regex is authoritative; LIKE only narrows candidates).
- Both headword-search and empty-query results are sorted by `alphabet_sort_key(sort_headword)` (see Collation Rules) where `sort_headword` is the headword text with any embedded `<n>` homonym content removed (`utils.content_rules.hw_text_excluding_n`, computed at DB build into the `dictionary.sort_headword` / `sub_headwords.sort_headword` columns).
- Headword search results keep their **display** headword (homonym number intact, e.g. `ґале́ра ІІ`); only the SORT key is stripped, so a homonym sorts by its base form: `гале́ра І, ґале́ра ІІ, ґалера абразоў, …`. Distinct `<entry>`s such as `ґен І` and `ґен ІІ` stay separate rows (equal sort keys → stable sort keeps file order).
- The preview page (`_show_previews`) groups by display headword but sorts by the `sort_headword` carried on each preview dict (built in `SearchEngine._preview_hw_fields`).
- Empty query returns ALL entries (dictionary + sub_headwords) deduplicated by `(id, headword)`, with `!SOURCES` filtered out.

### Collation Rules (`alphabet_sort_key` in `utils/text_utils.py`)
- Compares letter-by-letter using the Belarusian alphabet (`ґ` ranks after `г`, before `д`; `ё` is its own letter between `е` and `ж`).
- Combining accents (U+0300/U+0301) are skipped, so accented and unaccented letters compare equally — e.g. `ґазавы` sorts before `ґатунак`, and `ґаґаць` sits between `ґавыліць` and `ґазавы`.
- Word breaks (space, hyphen) are strong dividers ranked BELOW all letters (`-` = 0, space = 1; letters `а…я` = 2…34), so a multi-word entry groups immediately after its single headword: `ґаз, ґаз сьвяціць, ґаза, ґазавая ґрана́та, ґазавод, ґазавы, …`. Between the two break symbols space ranks after hyphen (so a hyphenated form sorts before the spaced form when otherwise equal).
- Among equal prefixes, shorter words come first (shorter-first), so `ґаз` precedes `ґаза` precedes `ґазаліна`.
- Other non-alphabet characters fall back to `len(alphabet) + ord(ch)` so they sort after letters with a stable relative order.
- Both the dictionary app and the markup app list sort through this single key; the XML files keep raw print order (see Source Data State), so file order and on-screen list order intentionally differ.

### Entry Formatting
- `entry_formatter.process_element` is recursive: processes children via `LinkHandler` for linkable tags (`src`, `st`, `see`), CSS‑class‑wraps others
- Each child's CSS class is applied by the **parent iteration** (not self-formatting) — no double-wrapping
- `<src>` links get `font-style: normal`; `<st>` links inherit italic
- `LinkHandler.create_link` handles source abbreviation resolution via `SourceMapper`
- `<tp>` gets its CSS class (`tp`) but no special styling beyond the class mapping
- **Comma-splitting quirks (preserve these):**
  - If a `<hw>` element's tail starts with `,`, the comma is split off and placed **inside** the `<span id="anchor">…,` so it stays part of the clickable/linkable anchor rather than dangling outside.
  - If a `<g>` element's tail starts with `,`, the comma gets its own `<span class="g">` wrapper and the remaining tail is plain text.
- `_sense_matches_headword` / sense targeting: a `<sense>` element is only considered if its `n` attribute matches a target sense (digit for numeric, string otherwise) AND (if it has an `hw` attribute) the target headword is among its pipe-separated variants, accent-stripped.
- Context (`FormatContext`) is module-level global state set via `set_target_subheadword` / `set_target_senses` / `clear_target`; `process_element` reads it to prepend `👉` arrows and wrap targeted senses/headwords in anchor spans.
- **Glyphs and schemes (single source):** `utils/constants.py` defines every emoji and URL scheme used across the apps — `ARROW_MARKER` (`👉`), `CROSS_MARKER` (`❌`), `BACK_ARROW` (`⬅️`), `FORWARD_ARROW` (`➡️`), `CHECK_MARK` (`✅`), `CHECK_BLANK` (`⬜`), `RADIO_ON` (`🟢`), `RADIO_OFF` (`⚪`), `GEAR_MARKER` (`⚙️`), `MAGNIFIER_MARKER` (`🔍`), `BOOKS_MARKER` (`📚`), `FLOPPY_MARKER` (`💾`), `COLLAPSED_TRIANGLE_ENTITY`/`EXPANDED_TRIANGLE_ENTITY` (`▶`/`▼`), and `SCHEME_WORD/SOURCE/PREVIEW/TOGGLE_SECTION`. Import the constant everywhere the glyph is needed — never re-type the emoji/entity/scheme string in widget code. The arrow is used in the entry view (`headword-arrow`/`sense-arrow`, entry_formatter.py) and passed to the sources panel renderer (`build_filtered_html`); the nav bar uses `BACK_ARROW`/`FORWARD_ARROW` (entry_viewer.py); the nav-bar close and sources-search close buttons use `CROSS_MARKER`. The emoji values are defined ONCE in `utils/constants.py` and imported everywhere — never re-type any of them in widget code.
- **Arrow-suppression for homonyms (HEADWORD arrow must NOT appear when opening a homonym whose number is a separate `<entry>`):** the decision of whether the opened headword is the *main* headword MUST compare against the full `<hw>` text via `SearchEngine.get_main_headword` (which uses `''.join(hw.itertext()).strip()`, accent-stripped by the caller), NEVER `hw.text` — `hw.text` alone drops an embedded `<n>` homonym numeral ("ґен " + "І") and makes the homonym wrongly look like a sub-headword, triggering the 👉 arrows. This rule applies in ALL navigation paths: entry-list click (`search_results_list.py`), see/word/nav links (`open_entry_by_headword` in `app/main_window.py`), and preview-link clicks (`preview:` handler in `app/main_window.py`). Sub-headword targets (e.g. a nested `<hw>` like `ґалера абразоў`) legitimately still get the arrow.
- **Italics rule:** `.g`/`.ex`/`.i` glosses are italic, but a nested `<hw>` inside a gloss (a "see" headword, e.g. `один <hw>ґалёш</hw>` in `ґалёшы`) and any inserted `👉` arrow stay **non-italic** — enforced by `font-style: normal` on `.hw`, `.headword-arrow`, and `.sense-arrow` (theme/widget_styles.py).

### Source Mapping (`SourceMapper`)
- Singleton (`__new__`), loads `data/source_mappings.json`, builds a variant→abbreviation map (`_variant_to_abbr`).
- **Space-prefix rule (preserve):** six abbreviations (`акр.`, `п.`, `пав.`, `р.`, `с.`, `вол.`) are in `_space_prefixed_only` and only match when preceded by a space or at position 0. This prevents false matches inside words (e.g. not matching `«п.»` inside `«ап.»`). Do NOT remove or generalize this whitelist.
- `get_abbreviation(text)`: exact match first, then longest-variant-first fallback.
- `extract_abbreviations(text)`: uses a compiled combined regex and returns `(abbr, variant)` pairs; same space-prefix check applies.

### Window Layout (`MainWindow.setup_ui`)
- Vertical main layout: top row (search box + sources button + settings button), bottom row (results list + splitter)
- Bottom row is `QHBoxLayout` (not a splitter): results list at stretch 0 (fixed 150px) + `bottom_splitter` at stretch 1
- `bottom_splitter` (`QSplitter` Horizontal) holds: entry viewer (initial `SPLITTER_ENTRY_INITIAL`=400px) + sources viewer (initial `SPLITTER_SOURCES_INITIAL`=400px)
- Both splitter panes are non-collapsible (`setCollapsible(0/1, False)`)
- Window default: 765x650px, minimum width dynamically computed as sum of visible panel minimums
- `_update_min_width()` recalculates on every show/hide of results list or sources panel
- Global stylesheet applied via `QApplication.instance().setStyleSheet(GLOBAL_STYLE)`; the results list uses `RESULTS_LIST_STYLE` (both in theme/widget_styles.py)

### Entry Viewer (`EntryViewer`)
- `DictTextBrowser` (QTextBrowser subclass) inside a QVBoxLayout with `NavigationBar` above it
- Read-only, no external links (`setOpenExternalLinks(False)`), `ClickFocus` policy
- Document margin: 15px left/right (`DOCUMENT_MARGIN`) via `rootFrame().frameFormat()` — **re-applied on every `setHtml`** because Qt resets the root frame format when HTML is set.
- `ENTRY_STYLESHEET` set as document default stylesheet for HTML rendering
- `stored_html` holds the last displayed HTML for refresh/restore
- `ScrollManager` handles anchor scroll, resize re-scroll, and cached state restore
- `setSource` overridden to block navigation for `word:`, `source:`, `preview:` schemes (checked against `SCHEME_WORD`/`SCHEME_SOURCE`/`SCHEME_PREVIEW` in `utils/constants.py`)

### Navigation Bar (`NavigationBar`)
- Fixed height 30px (`BAR_HEIGHT`), horizontal layout: Back | Back-spacer | Flex-spacer | Forward | stretch | Close
- Back/Forward buttons: 95px wide each (`NAV_BUTTON_WIDTH`), emoji labels (`BACK_ARROW`/`FORWARD_ARROW` + `strings.button.back/forward`), flat transparent style
- Close button: `IconButton`, 30x30px (`BUTTON_SIZE`)
- Visible only when `navigation_stack` has >1 entry
- Back button hidden when at index 0 (replaced by fixed-width invisible spacer to keep layout stable)
- History stack of `{headword, sense_parts}` dicts; `push()` truncates forward history on new push
- The preview sentinel `_PREVIEW_SENTINEL` (`'__preview__'`, a module constant in `app/main_window.py`) is used as a headword -- intercepted in `open_entry_by_headword` to restore preview

### Results List (`SearchResultsList`)
- Fixed width (`RESULTS_MIN_WIDTH` = 150px), horizontal scrollbar always off
- No focus policy on the QListWidget -- keyboard nav (Up/Down/Enter) routed via `SearchBox` signals; `ElidingDelegate`, `select_row`, `navigate_rows` live in `app/widgets/result_list_helpers.py`
- Custom `ElidingDelegate`: elides text exceeding `viewport().width() - RESULTS_ITEM_PADDING`px using `Qt.ElideRight`
- Tooltip shown only for items that overflow (text wider than viewport)
- **Tooltip width calculation must mirror the delegate's paint-time ellipsis decision, but at population time the viewport may not yet reflect the scrollbar.** So: `vw = viewport().width()` (stale width, still frame-aware) minus `verticalScrollBar().sizeHint().width()` ONLY when the list needs a scrollbar, minus `RESULTS_ITEM_PADDING`. Whether it needs a scrollbar is computed deterministically from `sizeHintForRow(0) * row_count > viewport().height()` (NOT `isVisible()`, which is stale pre-layout). This yields the correct tooltip per case — e.g. галоўны ґазавод (128px advance): scrollbar present → threshold 124 → tooltip shown; no scrollbar → threshold 136 → fits, no tooltip. Guard the equality edge: a threshold that lands exactly on the text advance (strict `>`) silently drops the tooltip.
- Tooltip text = `remove_accents(raw_headword)` -- accent-stripped headword
- Font: Cambria/Times New Roman serif, 12pt bold (via `GLOBAL_STYLE`)
- Item CSS in `RESULTS_LIST_STYLE`: left border 3px solid transparent (idle), grey on hover (`#c0c0c0`), blue on selected (`#7c9ec0`); background white -> `#fafafa` hover -> `#edf7fd` selected; text always black
- Items carry `UserRole` = entry_link, `UserRole+1` = raw headword
- First item auto-selected after `display_results`
- `display_results()` also clears entry viewer and scroll cache

### Search Box (`SearchBox`)
- `QLineEdit` subclass, fixed height 30px (`SEARCH_BOX_HEIGHT`)
- Signals: `navigate_up` (Up arrow), `navigate_down` (Down arrow), `activate` (Enter/Return)
- Style: white bg, 1px `#c0c0c0` border, 3px radius, 2px padding

### Settings Button (`SettingsButton`)
- Emoji gear icon (`GEAR_MARKER`), 30x30px (`BUTTON_SIZE`), opens `QMenu` on click
- Menu structure: heading -> separator -> `_belarusian_radio` "Belarusian" (with sub-options) -> `_russian_radio` "Russian"
- Built from a `_ToggleOption` base with `_RadioOption` and `_CheckOption` subclasses; radios use `RADIO_ON` (green circle) / `RADIO_OFF` (white circle) glyphs; sub-options use `CHECK_MARK`/`CHECK_BLANK` glyphs, indented 24px left margin, and are inserted BEFORE the russian radio in the menu (`_add_scope_option` + `_scope_actions`)
- Sub-options (Belarusian): at least one must remain checked — `_sync_sub_options` disables the only-checked one (via `_CheckOption.set_active`, which applies `COLOR_DISABLED_FG`)
- `_headwords_option()` / `_examples_option()` return the two sub-options; `_update_sub_visibility` hides/shows them when the russian radio is active
- `get_option_states()` returns the three search options dict (see Search Modes for the exact state mapping)

### Sources Panel (`SourcesPanel`)
- `DictTextBrowser` (read-only) + search `QLineEdit` + magnifier `IconButton` (`MAGNIFIER_MARKER`) + close `IconButton` (`CROSS_MARKER`), in a VBox layout; `get_widget()` returns the container
- Toggle button (`SourcesButton`): book emoji (`BOOKS_MARKER`), 30x30px, `MENU_BUTTON_STYLE`
- Loaded from `data/sources.xml`; HTML built by `sources_renderer.build_filtered_html` (`SourcesRenderer` API is `build_filtered_html`, `section_matches`, `compile_search_regex`)
- Search box filters/sections by text match; a search matching no section renders `strings.no_results`
- When `sources.xml` contains no `<entry>` children, the panel content is `'<body></body>'` (an empty page; no message string is used)
- Panel shown/hidden via toggle button; visibility tracked in `sources_visible`
- **Collapse/search state machine (preserve):** `_collapsed_sections` (a set) tracks collapsed `<section>` ids. Search **auto-expands** collapsed sections that match; on clearing the search, the pre-search collapsed state is restored. Hiding the panel resets all collapsed state and the anchor.
- Section toggle links use the `SCHEME_TOGGLE_SECTION` scheme (`toggle-section:{id}`), rendered by `sources_renderer` with `COLLAPSED_TRIANGLE_ENTITY`/`EXPANDED_TRIANGLE_ENTITY`; the arrow headword marker (`ARROW_MARKER`) is passed in and injected at the current anchor
- `scroll_to_source(abbr)`: strips trailing `:`/`.` from the abbreviation for anchor lookup, auto-expands collapsed sections containing the target, calls `QApplication.processEvents()` before scrolling so layout is computed.
- `SourcesToggle` (app/panels/sources_toggle.py) resizes the splitter (half entry / half sources) on show; on hide it combines entry+sources width back.

### Scroll Manager (`ScrollManager`, `utils/scroll_manager.py`)
- `scroll_to_anchor(anchor)`: calls `viewer.scrollToAnchor(anchor)` and records `last_anchor`
- `handle_resize()`: re-scrolls to `last_anchor` if set (no debounce timers)
- `cache_state()` / `restore_state()`: save/restore the full HTML + scrollbar value across content refreshes
- `save_scroll()` / `restore_content(html)`: save only the scrollbar value, or set HTML and restore the saved scroll
- `clear_cache()`: clears cached HTML/scroll and `last_anchor`
- `last_anchor` is cleared to `None` after every `display_entry` and `clear_cache`.

### Link Routing (`on_link_clicked` + `open_entry_by_headword`)
- URL schemes (`SCHEME_WORD`/`SCHEME_SOURCE`/`SCHEME_PREVIEW` in `utils/constants.py`): `word:`, `source:`, `preview:`. All routed through `LinkHandler.process_url` / `on_link_clicked` (see Entry Viewer for `setSource` blocking). `process_url` returns `(link_type, target, sense_parts, entry_link)`.
- **`<see>` with a homonym `<n>`**: the target string is built from the whole `<see>` content (`itertext`, which includes an embedded `<n>` numeral), so `<see>грыжа <n>ІІ</n>, 1, 2</see>` renders the full `грыжа ІІ, 1, 2` as a `word:` link to headword `грыжа ІІ` with sense parts `[1, 2]`. `LinkHandler.parse_link_text` is token-based: it detaches a *trailing* sense list (digit or single-letter tokens) from the word, and any trailing Roman-numeral token after the word (Cyrillic `І`/`і` or Latin `I`/`i`, `V`, `X`) stays on the word as the homonym marker. `get_entry_by_headword` falls back to comparing accent-stripped *display* headwords when the stripped normalized index has no match — required because homonyms are indexed n-stripped (`грыжа ІІ` → `грыжа`).
- **Preview links** (`preview:{entry_id}|{anchor}`): URL-decode the anchor if it contains `%`, look up the result in `current_results` first then fall back to `SearchEngine.get_entry_row(entry_id)`, set `_highlight_entry = True`, save `_last_preview_html`, and push the headword onto the nav stack with `_PREVIEW_SENTINEL` as the older entry (Back returns to the previews).
- **`_PREVIEW_SENTINEL`** (`'__preview__'`): `open_entry_by_headword` intercepts `headword == _PREVIEW_SENTINEL` and calls `_restore_preview()` (restores `_last_preview_html`, clears display state and nav bar). Preserve this sentinel and set `_highlight_entry = True` whenever a preview link is followed.
- `open_entry_by_headword(headword, sense_parts=None, entry_link=None, from_navigation=False)`:
  - `_PREVIEW_SENTINEL` → restore preview and return.
  - Resolves the entry: by `entry_link` (searches `current_results`, then `SearchEngine.get_entry_by_link`) or by headword (searches `current_results` exact, then accent-stripped, then the DB). Parses the resolved entry via `get_parsed_entry` (shared cache via `get_main_headword`).
  - Sets format target: `set_target_senses(sense_parts, headword)` if sense_parts given; else `set_target_subheadword` if accent-stripped target differs from main headword; else `clear_target()`.
  - Pushes to nav stack only when NOT `from_navigation` and headword changed; if the previous headword was None but `_last_preview_html` exists, pushes `_PREVIEW_SENTINEL` as the older entry.
  - **Unresolved target:** when the headword/link resolves to nothing (e.g. a `<see>` to a word absent from the dictionary), the navigation is NOT a no-op — it becomes an explicit EMPTY step: pushes the target on the nav stack (same old-headword/`_PREVIEW_SENTINEL` rules) and displays an empty `<body></body>` window. This keeps Back/Forward in increments (empty → previous entry → … → preview) in every search mode.
  - Scrolls to the appropriate anchor (`sense_{n}`, link `#hash`, or the headword).

### Highlighting
- Entry opened from preview -> search terms highlighted with `#FFF9C4` background (`COLOR_HIGHLIGHT_BG` in theme/widget_styles.py)
- Same-entry see links preserve highlight (`_highlighted_entry_id` matches); different-entry see links clear it
- Close button on navigation bar -> `_dismiss_highlight()` re-renders without highlight
- Highlight applied via `SearchEngine.apply_highlight` — the excluded classes match the Exclusion Rules table (enforced by `_should_exclude_from_highlight`):
  - protects `<a>` tags and excluded class blocks via `_protect_class_blocks` (manually tracks `<span>` nesting depth to find the matching close)
  - **preview mechanism:** excluded children are wrapped in `<span class="search-excluded">` and passed as `exclude_classes=[_EXCLUDED_HIGHLIGHT_CLASS]`; protected blocks become `\x00A{idx}\x00` placeholders, so the regex only ever scans the highlightable (indexed-equivalent) text — excluded fragments are rendered but never highlighted
  - text parts containing a placeholder are sub-split on `(\x00[^\x00]*\x00)` so a protected block never merges adjacent plain text into one skipped part
  - runs `finditer` across concatenated text parts, maps highlights back to individual parts, restores placeholders twice (to handle nesting)
- In `MainWindow.display_entry`, the exclude set starts with `hw` **always**. When `_search_normalize` is True (translations-only), `ex` is also excluded. When `_search_in_headwords` is True, `t` is excluded. `<hw>` must NEVER be highlighted in any Belarusian-headword search variant.

### Global Shortcut
- Ctrl+C copies selection from any QTextEdit via `install_global_copy` in `app/shortcuts/shortcuts.py`

## Writing Conventions
- No comments in code unless essential
- Module-level constants, no inline literals (use `theme/layout_constants.py` for metrics, `utils/constants.py` for glyphs/schemes, `theme/widget_styles.py` for colors/styles)
- All CSS in `theme/widget_styles.py` (one source of truth; `RESULTS_LIST_STYLE` included)
- Qt signals for cross-component communication
- Private methods use `_` prefix
- Pane = self-contained UI component (EntryViewer, SourcesPanel, SearchResultsList)
- Window = top-level OS window (MainWindow)
- **Docs must stay de-duplicated**: state each fact in exactly ONE place; where a later section would repeat it, use a `see <section>` cross-reference instead of restating it. Restating creates drift when code changes and only one copy gets updated.

## Database Schema
- `dictionary` table: `(id INTEGER PRIMARY KEY, headword, sort_headword, normalized_headword, full_entry, entry_link, source_file)`
- `sub_headwords` table: `(id, headword, sort_headword, normalized_headword, main_entry_id)` — sub-headwords share parent entry
- `content_index` table: `(entry_id, tag_type, searchable_text)` — pre-built index for translation/examples search
- `source_file` column tracks which file in `data/dictionary/` each entry came from (used by markup app for save)

## Build / Rebuild
- Entry points: `run.py` (dictionary app) and `run_markup.py` / `markup/main.py` (markup app) all construct `QApplication` first, then the respective window with `create_search_engine()` from `db.bootstrap`.
- `create_search_engine()`: checks `needs_rebuild()` (True if the DB is missing, `data/sources.xml` is newer than the DB, or ANY file in `data/dictionary/` is newer), rebuilds if stale, then returns `SearchEngine(db_path)`.
- `build_database()` iterates `data/dictionary/` files in sorted filename order and reads only `.xml` files (skips `.txt` and directories), plus `sources.xml` (`source_file='sources.xml'`). It reuses the existing DB file (drops/recreates the three tables) rather than `os.remove`-ing it, so a second process holding the DB open does not block a rebuild on Windows. `get_source_path(source_file)` maps a `source_file` (e.g. `'sources.xml'` or a split file name) to its absolute path; both apps use it instead of re-deriving paths.
- At build time the SAME exclusion rules as the search engine are used when building `content_index` (see Exclusion Rules). Translation index text is normalized with `normalize_jo(remove_accents(...))`; example index with `remove_accents(...)` only (no ё→е).
- `normalized_headword = remove_accents(sort_headword).lower()` at build time — i.e. computed from the n-stripped headword, so embedded `<n>` homonym numbers are NOT searchable/indexable (typing `І` matches nothing; `ґен` still matches `ґен І`/`ґен ІІ`). The regex re-filter in `_search_headwords` likewise matches the n-stripped text (`r[5] or r[1]`) so a wildcard query can't match a homonym number.
- `sort_headword` = headword text with embedded `<n>` homonym content removed (`hw_text_excluding_n`), used for the entry-list ordering and as the search-discriminated text; the `headword` column keeps the full text (homonym numbers displayed).

## Key UI Wiring to Preserve
- **Settings button `_consume_next_press`**: after the menu closes (`aboutToHide`), if the cursor is still over the button, `_consume_next_press` is set so the mousePressEvent consumes the release and the menu does NOT immediately re-open. Keep this workaround.
- **`show_all_entries()` first-show guard**: runs on the FIRST `showEvent` only (guarded by `_initial_shown` via `getattr`), so the initial entry load happens after the window is visible. Both the dictionary app and markup app use this.
- **`SearchResultsList.on_clicked`** resolves the clicked item by accent-stripped headword, computes `<hw>` equality via `SearchEngine.get_main_headword`, sets `set_target_subheadword` when the clicked headword differs from the main headword, then `display_entry` + scroll.
- **Combined-mode result click**: when clicking a headword match while `_last_preview_html` exists, `_PREVIEW_SENTINEL` is pushed onto the nav stack so Back returns to the previews.