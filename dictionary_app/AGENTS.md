# Dictionary App — Architecture Guide

## Goal
A Belarusian–Russian bilingual dictionary app. Queries in either language search headwords (Belarusian), translations (Russian `<t>` tags), or examples (`<ex>` tags), with tab‑separated search modes and a split‑pane UI.

A separate **markup app** (`markup_app/AGENTS_markup.md`) provides an entry editor that saves changes back to the source XML files.

## Project Layout
```
stankievichau_slounik/          # project root (git repo)
├── dictionary_app/             # dictionary app - shared modules live here
│   ├── __init__.py             # exports MainWindow (from .main_window)
│   ├── main_window.py          # Main window, wiring, orchestration
│   ├── panels/                 # Pluggable UI panes
│   │   ├── entry_viewer.py        # Entry display + navigation bar
│   │   ├── search_results_list.py # Headword results list
│   │   ├── sources_panel.py       # Sources panel (viewer + search + magnifier button)
│   │   ├── sources_renderer.py    # Sources XML → HTML (build_filtered_html)
│   │   └── sources_toggle.py      # Splitter resizing helpers when toggling sources
│   ├── widgets/                # Reusable Qt widgets
│   │   ├── dict_text_browser.py   # QTextBrowser: block word/source/preview routes, keep margins
│   │   ├── icon_button.py         # Flat icon button
│   │   ├── menu_button.py         # MenuButton base (fixed 30x30, class="menu-button", MENU_BUTTON_STYLE)
│   │   ├── search_box.py          # QLineEdit with keyboard nav signals
│   │   ├── settings_button.py     # Settings gear button + menu (search-mode options)
│   │   ├── sources_button.py      # Sources toggle button
│   │   ├── insert_letter_g.py     # InsertLetterGButton - momentary ґ (U+0491) letter-insert button
│   │   └── result_list_helpers.py # ElidingDelegate, select_row, navigate_rows, clamped_row
│   ├── shortcuts/
│   │   └── shortcuts.py  # Global Ctrl+C handler
│   ├── build/                # SQLite database output (gitignored)
│   │   └── dictionary.db
│   ├── data/
│   │   ├── dictionary/       # Split XML entry files (dictionary_A.xml …); raw OCR text in raw_data/
│   │   ├── sources.xml       # Sources/abbreviations reference
│   │   └── source_mappings.json
│   ├── db/                   # Database layer
│   │   ├── search_engine.py  # SearchEngine - all query logic
│   │   ├── build_database.py # Build/incrementally rebuild SQLite from XML (mtime-based stale set)
│   │   └── bootstrap.py      # create_search_engine(): stale_source_files() + incremental build, then open
│   ├── format/               # Entry formatting pipeline
│   │   ├── entry_formatter.py  # XML → HTML formatter
│   │   ├── link_handler.py     # Link creation (<a> tags) + URL routing
│   │   └── source_mapper.py    # Abbreviation → source-id mapper
│   ├── localization/
│   │   ├── loader.py         # strings object from JSON
│   │   └── strings.json      # dictionary-app strings
│   ├── theme/
│   │   ├── layout_constants.py  # Pixel/metric constants
│   │   └── widget_styles.py     # Global + per-widget stylesheets, named palette + RESULTS_LIST_STYLE
│   ├── utils/                # shared helpers (constants, xml_schema, text_utils, search_regex, scroll_*, content_rules)
│   ├── AGENTS.md             # This file (dictionary app guide)
│   └── run.py                # Dictionary app launcher
└── markup_app/               # separate markup app - see markup_app/AGENTS_markup.md
```

## Key Design Decisions

### Search Modes
- Three boolean options: `search_in_headwords`, `search_in_translations`, `search_in_examples`
- **Exclusive mode**: exactly one of translations/examples ON, headwords OFF — shows preview snippets in the entry pane, hides the results list
- **Combined mode**: headwords ON + examples ON, translations OFF — headword matches fill the results list, example matches fill previews
- **Any other combination** (or headwords-only) → standard headword search with results list visible
- Empty main-search results leave the entry pane empty (the results list is cleared). The "no results" message (`strings.nav.no_results`, "Няма вынікаў.") is used ONLY by `sources_renderer.build_filtered_html` when a sources search matches no section.
- **Settings state machine** (`SettingsButton.get_option_states`): `_russian_radio` → `{headwords:False, translations:True, examples:False}`; `_belarusian_radio` → `{headwords:_headwords_option(), translations:False, examples:_examples_option()}` — translations is ALWAYS False for Belarusian. Sub-options (Belarusian) control headwords + examples only.
- **Combined mode does a dual search**: `on_search` runs TWO separate `search_engine.search()` calls (headwords-only fills the list, examples-only fills previews). This keeps the results list showing only headword matches. Do NOT collapse this into a single call.
- **Headword search shows duplicate rows by design**: `_HEADWORD_ROWS_SQL` joins the `dictionary` and `sub_headwords` selects with `UNION ALL` (not `UNION`), so an entry whose sub-headwords include a duplicate of itself appears as multiple identical list rows (e.g. searching `зачапіцца` returns id 88 twice). Keep it `ALL` — the markup duplicate-group filter relies on every row being visible. The results LIST then collapses same-entry duplicates to a single row via `dictionary_app.utils.text_utils.collapse_same_entry_duplicates` (key = DB entry id + accent-stripped headword, first occurrence wins) — genuine homonyms in DIFFERENT entries are kept, and the SQL is never narrowed.

### Content Index
- `content_index` table in `dictionary.db`: `(entry_id, tag_type, searchable_text)` + indexes
- Built by `build_database.py` — extracts `<t>`/`<ex>` text at build time with same exclusion rules as the search engine
- Translation/examples search first consults the trigram FTS5 indexes (`content_fts_t`/`content_fts_ex`, populated from `content_index`) for query spans ≥3 characters, then falls back to `LIKE '%…%'` over `content_index` for shorter spans; it then fetches and parses only the matching entries to build previews. Parsed roots live in the bounded `_parsed_cache`; preview results are cached in the bounded `_preview_cache` (see Scale Notes).
- `SearchEngine.get_parsed_entry(entry_id, xml_string)` parses an entry XML once and caches the root in `_parsed_cache` keyed by `entry_id`. It is reused wherever entry roots are needed (`_annotate_content_matches`, `get_main_headword`, preview-link clicks) so the same entry is never re-parsed per action. The cache is an **LRU** (`collections.OrderedDict`): accesses `move_to_end`, inserts evict the least-recently-used entry once the bound (`_PARSED_CACHE_MAX_SIZE = 512`) is exceeded — so it never grows without limit. Eviction is per-entry by design: a miss just reparses that `xml_string` (callers always supply it), so no event-based bulk clearing is warranted.
- `SearchEngine.get_main_headword(entry_id, xml_string)` returns the FIRST `<hw>` in document order's full text (`''.join(element.itertext()).strip()`), including any embedded `<n>` and any `excl` variant — the canonical main-vs-sub comparison text for arrow decisions. It deliberately does NOT skip `excl` (that is the "excl still participates in the pointing-finger logic" part).

### Exclusion Rules
| Context | Excluded elements |
|---|---|
| Translation (`<t>`) search indexing | `<src>`, `<st>`, `<g>`, `<see>`, `<i lang="vl">`, `<i excl="true">`, `<lang code="vl">`, `<lang code="la">`, `<lang excl="true">` |
| Translation preview highlight | Same as indexing — excluded children rendered but not highlightable |
| Example (`<ex>`) search indexing | `<src>`, `<st>`, `<i lang="ru">`, `<lang code="ru">` |
| Example preview highlight | Same as indexing |
| Headword (`<hw>`) row indexing | `<hw excl="true">` |

### `<hw excl="true">` (excluded headword)
- A `<hw>` carrying an `excl` attribute (any value, e.g. `excl="true"` — same convention as `<i excl="true">`) is excluded from ALL index/logic: it never becomes a `dictionary` or `sub_headwords` row (so it never appears in the entry list, headword search, empty query, or collation; the entry is indexed under its first non-excl `<hw>` instead) and is skipped in `d_hw_variants` / preview-headword aggregation (`_preview_hw_fields`).
- It is STILL rendered in the entry display (bold, anchor id, comma-absorption) and STILL participates in the pointing-finger (`👉`) logic — which is the ONLY logic it stays in: `SearchEngine.get_main_headword` (the main-vs-sub finger comparison) does NOT skip it, and `is_target_headword` can point at it. Concretely in `•<hw excl="true">ёсьць</hw>, <hw>ёсьцяка</hw>` the comparison main is `ёсьць`, so clicking the listed `ёсьцяка` row hits the `result[1] != main_headword` branch and points 👉 at `ёсьцяка`, exactly like a sub-headword — WITHOUT any change to the entry-list-click finger logic.
- Data example (`dictionary_Jo.xml`): `•<hw excl="true">ёсьць</hw>, <hw>ёсьцяка</hw>,—<i>см. под <see>ё</see>.</i>` — an homographic cross-ref variant that must not be indexed (real `ёсьць` stays indexed as a sub-headword of the `ё` entry) yet stays visible in the entry's headword line.
- Applied at DB build (`build_database.py`: main row = first non-`excl` `<hw>`, sub-rows skip `excl`), preview headword aggregation, and `d_hw_variants`. The finger logic in `entry_formatter.py` and `get_main_headword` intentionally do NOT skip them.

### Source Data State (`<tp>` / `lvl`)
- All `dictionary_app/data/dictionary/dictionary_*.xml` source files are stripped of every `<tp>` tag and `lvl` attribute — inner text is kept, only bare `<t>` tags remain. This is a **data-only** change.
- ґ-initial entries live in `dictionary_app/data/dictionary/dictionary_G.xml` (untracked; the tracked `dictionary_app/data/dictionary/dictionary_*.xml` set does not include G). The authoritative OCR text is `dictionary_app/data/dictionary/raw_data/dictionary_G_raw.txt` (also untracked) — when editing or reconstructing G entries, verify against the raw lines. Since `dictionary_G.xml` is untracked, remember it is NOT part of `git status`; rebuilds/saves still target the file via `get_source_path`.
- The lexicographic XML markup conventions (tags, entry shapes, spacing, OCR-fix rules, homonym/`link` handling) used when transcribing raw OCR text are documented in `markup_app/MARKUP_PATTERNS.md` — see there for tagging rules; this file covers only app behavior.
- `dictionary_G.xml` is kept in the raw file's print order (anchored to `dictionary_G_raw.txt`). The on-screen list order is alphabetical regardless of file order because search results are sorted by `alphabet_sort_key` (see Collation Rules) — so file order and list order are intentionally different. All other letter files are also in print order; none should be re-sorted alphabetically in the files.
- All app code support for `<tp>`/`lvl` has been removed: no ranking tiers remain (the former `lvl="1"`-based tiers, `_compute_t_match_rank`, and `_tier_for_match` are gone — previews carry no `rank` and sort purely alphabetically by `sort_headword`, see Wildcard / LIKE building), and `entry_formatter` no longer maps a `tp` CSS class. Re-adding `<tp>`/`lvl` to the data would require restoring the rank pipeline. The markup editor's `tp`/`lvl="1"` tag buttons were removed too (markup is written by hand or with the remaining tag buttons).

### Cross-Reference IDs (`<hw id>` / `<see>`)
- 15 letter files, **2 entry-level `hw_xml_id`s** (`аборка` = `абора_бечевка`, `юрый`… see the ID list in markup notes) and **6 `<hw id>` sub-headword IDs** across A/Ch/DZ/G/Jo. All six resolve; `word:` and markup lookups go through `get_entry_by_xml_id` / `get_entry_sub_headword`.
- `<see>` census: 1 entry-only (`<see entry="абора_бечевка">аборка</see>` in A), 12 bare-`hw` sees, 91 text-only sees. **No `link=` attribute and no `#` remain in any source file.**
- `юр` intentionally has no XML ID and resolves by de-accented text fallback. Undeclared ID references that do not exist in any entry (`паветка`, `чэмер`, `а ІІІ`, `чапяла`, `плаксуха`, `бязножнік`) stay as-is and degrade to text matching or a dead link.
- Five sense links in `dictionary_G.xml` point at words absent from the corpus (`цюмкі` 2, `цюнкі` 2, `зык` 3/4/5). They are pre-existing data gaps, not link-handler bugs: they take the documented unresolved-target empty step.

### Preview System
- Translation previews: sense number prepended as `<span class="{num_tag}">` — `num_tag` is the sense's `<n>` element when present (falling back to `<b>`); **unless** the matched `<t>` belongs to a sub-headword `<d>` nested inside the sense (walk from the `<t>` to the `<sense>` crossing a `<d>`), in which case NO sense number is prepended — a sub-headword (e.g. `ґарба́рны промысл`) is its own entry and must not carry the enclosing main sense's number. When a matched `<t>` is directly preceded by an `<ex>` with `—` tail, the whole `<ex>—<t>` block is emitted as `<span class="g">…</span>—` + the `<t>` preview; **if the `<ex>` is itself preceded by a `<t>`** (the `t . ex — t` chain), that preceding `<t>` is included as leading context too (`<span class="t">…</span>` + its tail), mirroring the embedded-t-in-ex path (the «щи»/гарох pattern). No context is taken from siblings further back (this avoids leaking unrelated elements like a headword separator `<b>:</b>` into the preview).
- **Absorbed-`<t>` suppression (translation only):** when a matched `<t>` is immediately followed by an `<ex>` (with `—` tail) whose next sibling is another matched `<t>`, the earlier `<t>` becomes the leading context of the later one and is NOT emitted as its own standalone preview — this avoids duplicating it (e.g. `в лицо` matched twice shows as one `в лицо. У вабліччу… —в лицо мне…` preview).
- **Sense-number dedup (translation only):** the sense number is prepended at most ONCE per enclosing sense across all previews of an entry — `highlight` tracks `emitted_sense_ids` and suppresses the number for later matches inside the same sense (e.g. query `*о*` on `юха` matched two `<t>`s inside sense `n="3"`: only the first preview carries `3.`, the second shows the gloss unprefixed). Both the embedded-`<t>`-in-`<ex>` builder and the plain builder share this: `_build_embedded_t_preview` marks its sense emitted, and `_build_preview_html(..., add_sense_num=False)` suppresses for subsequent same-sense matches.
- **Secondary-`<t>` gating (translation only):** after a matched primary `<t>`, a trailing `<ex>—<t>` chain is appended ONLY when the secondary `<t>` also matches the query (same `content_text` + `normalize_jo_to_je` normalization as `find_content_matches`); a non-matching secondary drops the whole `<ex>—<t>` chain instead of showing unhighlighted gloss context (e.g. `Юрка` query `юр` keeps `Георгий, Юрий` but drops `Не па Юрку шапка…—овес не по коню`). The leading-context rule above is NOT gated: an unmatched preceding `<t>` still renders as leading context when the trailing `<t>` matched.
- Example previews: trailing `—<t>` appended as `<span class="t">` when pattern detected
- Multiple matching elements with the same headword within one entry are **grouped** into one preview
- Results are deduplicated by `entry_id`; a deduped row attaches **all** of the entry's matches as previews (across every sub-headword) — the surviving headword is NOT used to filter the preview list
- Preview spacing: `<br>` between sense previews only when `<br>` exists in the raw XML between matched elements; ` <br><br>` between headword groups
- Preview headwords are clickable links (`preview:{entry_id}|{headword}`) — clicking opens the full entry with search-query highlighting
- **Preview headword aggregation (`_preview_hw_fields`):** a matched element inside a `<d>` → its ancestor `<d>`'s direct `<hw>` children joined with `|` (plus the n-stripped sort variant); otherwise the entry's `<hw>`s that sit **outside any sense OR inside the same sense as the match** (via `_enclosing_sense`) are joined with `|` (entry with no `<d>`), or the first of those taken (entry that has `<d>`s elsewhere but whose match is outside one) — secondary headwords living in OTHER senses (e.g. `ґатунак воўны` for a sense-1 match) are NOT appended. Fallback to the caller's headword if nothing qualifies. The results list renders `|` as `, ` and scrolls to the first headword. Works for any number of `<hw>`s in both the d-ful and d-less cases. `<hw excl="true">` elements are skipped in both the `<d>` (`d_hw_variants`) and the non-`<d>` (`root.findall('.//hw')`) aggregation paths, so an excluded headword never becomes a preview headword.

### Search Regex (`compile_search_regex`)
- Accent-insensitive: every literal character accepts optional combining marks U+0300/U+0301 via `_ACCENT_COMB`
- Wildcards: `*` → one or more word chars, `?` → one word char, stop at whitespace
- Custom word-boundary lookarounds: `(?<![\w\'\u2019\u02BC-])` / `(?![\w\'\u2019\u02BC-])` — treats punctuation as boundaries, apostrophe and hyphen as word chars
- Trailing space in query → exact-word match (adds trailing boundary)
- Multi-word queries: regex `\s+` between word patterns
- `ё`↔`е` mapping (`normalize_jo`) — see Accent-Handling Chain for where it applies

### Accent-Handling Chain
`remove_accents` is applied at EVERY layer: SQL `normalized_headword` at build time, query normalization, result-list item display text, entry-link matching, and preview headwords. Never drop an accent-strip step on one layer only — it must stay consistent across build, search, and display.
- `normalize_jo` (`ё`→`е`, `Ё`→`Е`) in `dictionary_app/utils/text_utils.py` is applied **only** for translation search (`tag='t'`), never for examples.
- The content-search regex (`_search_via_index`, used for `t`/`ex`) is built from the query with accents stripped (`remove_accents(text.strip())`) and, for `t` only, `normalize_jo_to_je` applied — mirroring the headword path (`compile_search_regex(clean_text, …)` where `clean_text = remove_accents(text.strip())`). Candidate narrowing still goes through `index_text`/FTS/LIKE; the regex that re-filters is always the de-accented one, so accented or `ё`-spelled queries still match.
- In `MainWindow.on_search`: `_search_normalize` is set True only when translations-only (translations ON and examples OFF); `_search_in_headwords` mirrors the option. These flags steer which classes get highlighted (see Highlighting).

### Wildcard / LIKE building
- Headword search narrows candidates via the `headword_fts` trigram index when the query's longest alphanumeric span is ≥3 chars, otherwise via a SQL `LIKE` pattern (`?` → `_`, `*` → `%`, wrapped in `%`) over the normalized headword columns with `collapse_spaces=True`; both paths then re-filter results by the compiled regex on the accent-stripped, case-preserving display headword (`remove_accents(r[1])`; regex is authoritative — FTS/LIKE only narrow candidates).
- Both headword-search and empty-query results are sorted by `alphabet_sort_key(sort_headword)` (see Collation Rules) where `sort_headword` is the headword text with any embedded `<n>` homonym content removed (`dictionary_app.utils.content_rules.hw_text_excluding_n`, computed at DB build into the `dictionary.sort_headword` / `sub_headwords.sort_headword` columns).
- Headword search results keep their **display** headword (homonym number intact, e.g. `ґале́ра ІІ`); only the SORT key is stripped, so a homonym sorts by its base form: `гале́ра І, ґале́ра ІІ, ґалера абразоў, …`. Distinct `<entry>`s such as `ґен І` and `ґен ІІ` stay separate rows (equal sort keys → stable sort keeps file order).
- The preview page (`_show_previews`) groups by display headword but sorts by the `sort_headword` carried on each preview dict (built in `SearchEngine._preview_hw_fields`).
- Empty query returns ALL entries (dictionary + sub_headwords) deduplicated by `(id, headword)`, with `!SOURCES` filtered out.

### Collation Rules (`alphabet_sort_key` in `dictionary_app/utils/text_utils.py`)
- Compares letter-by-letter using the Belarusian alphabet (`ґ` ranks after `г`, before `д`; `ё` is its own letter between `е` and `ж`).
- Combining accents (U+0300/U+0301) are skipped, so accented and unaccented letters compare equally — e.g. `ґазавы` sorts before `ґатунак`, and `ґаґаць` sits between `ґавыліць` and `ґазавы`.
- Apostrophes (`'`, `’`, `ʼ`) are skipped entirely (not ranked), so `Юр'е` collates exactly as `Юре`.
- Word breaks (space, hyphen) are strong dividers ranked BELOW all letters (`-` = 0, space = 1; letters `а…я` = 2…34), so a multi-word entry groups immediately after its single headword: `ґаз, ґаз сьвяціць, ґаза, ґазавая ґрана́та, ґазавод, ґазавы, …`. Between the two break symbols space ranks after hyphen (so a hyphenated form sorts before the spaced form when otherwise equal).
- The pipe `|` (used to join multiple `<hw>`s of one entry into a preview sort key) is ranked like a space, so a completed first headword sorts before any longer word with the same prefix — `ё|ёсьць|ёсьцека` precedes `ёвінны`; groups sharing a first headword tie-break by second, then third, … headword (`ё|ёсьці|ёсьцека` before `ё|ёсьць|ёсьцека`, since `і` ranks before `ь`).
- Among equal prefixes, shorter words come first (shorter-first), so `ґаз` precedes `ґаза` precedes `ґазаліна`.
- Case is NOT baked into the letter rank: uppercase letters only decide ties AFTER the character ranks, so `юр` sorts before `Юр` (and `юрка` before `Юрка`). `alphabet_sort_key` therefore returns a `(ranks, case_flags)` pair — Python compares the `ranks` lists first and only falls back to `case_flags` for otherwise-equal keys.
- Other non-alphabet characters fall back to `len(alphabet) + ord(ch)` so they sort after letters with a stable relative order.
- Both the dictionary app and the markup app list sort through this single key; the XML files keep raw print order (see Source Data State), so file order and on-screen list order intentionally differ.

### Entry Formatting
- `entry_formatter.process_element` is recursive: processes children via `LinkHandler` for linkable tags (`src`, `st`, `see`), CSS‑class‑wraps others
- Each child's CSS class is applied by the **parent iteration** (not self-formatting) — no double-wrapping
- `<src>` links get `font-style: normal`; `<st>` links inherit italic
- `LinkHandler.create_link` handles source abbreviation resolution via `SourceMapper`
- **Comma-splitting quirks (preserve these):**
  - If a `<hw>` element's tail starts with `,`, `:` or `;`, the symbol is split off and placed **inside** the `<span id="anchor">…,` / `<span id="anchor">…:` / `<span id="anchor">…;` so it stays part of the clickable/linkable anchor (rendered bold with the headword) rather than dangling outside. Two duplicate commas `,,` after `</hw>` are both split off and placed inside the anchor (both stay bold).
  - If a `<g>` element's tail starts with `,`, the comma gets its own `<span class="g">` wrapper and the remaining tail is plain text.
- **Paren rule (symmetric to the comma rule, same logic in `process_element`):** any literal `(` / `)` occurring inside an italicized tag's text (`g`, `ex`, `i`, `st`, `see`) is auto-wrapped in `<span class="p">` at render time, so the parens stay non-italic even if the markup does **not** surround them with `<p>`. `<p>` markup in data still works and is redundant (presents identically). `<src>` (already `font-style: normal`) is exempt.
- **Embedded-`<p>`-in-`<st>` rule:** a `<p>` child inside a `<st>` (or `<src>`/`<see>`) element is preserved as `<span class="p">…</span>` in the **inner-content loop** of `process_element` (NOT flattened to bare text), so register/style markers like `<st><p>презр.</p></st>` render plain (`.p` is `font-style: normal; font-weight: normal;`) inside the otherwise italic `<st>`.
- **Square-bracket bold rule (preserve):** a literal `[` … `]` pair whose inner content contains **only** `<hw>` and/or `<src>`/`<st>` elements (at least one `<hw>`) is auto-wrapped in `<b>` at render time, so such brackets stay bold even if the markup does **not** surround them with `<b>`. Detection (`_find_bracket_bold` in `entry_formatter.py`) scans the element's text and each child's tail and requires the `[` and `]` to be sibling text directly around the qualifying tags. Other bracket usages (e.g. brackets around non-`hw`/`src`/`st` content) are left untouched.
- `_sense_matches_headword` / sense targeting: a `<sense>` element is only considered if its `n` attribute matches a target sense (digit for numeric, string otherwise). `<sense>` has NO `hw` attribute (support removed) — sense→headword binding is only via the enclosing `<d>` bucket (`current_variants`).
- Context (`FormatContext`) is module-level global state set via `set_target_subheadword` / `set_target_senses` / `clear_target`; `process_element` reads it to prepend `👉` arrows and wrap targeted senses/headwords in anchor spans. It is **cleared by `format_entry` after every render**, so it is write-only for the caller and must never be read back to learn what was applied (see Navigation History). The sub-headword target is applied to EVERY matching `<hw>` (matched by its `id` attribute or by de-accented text) — so a same-entry duplicate headword points the `👉` at all of its occurrences at once, not just the first.
- **Anchor IDs for a scoped target are entry-local:** a `<hw>` gets `id` = its `id` attribute when present, else `remove_accents(text)`. There is no entry-ID prefix, because the anchor is only ever looked up inside the already-resolved entry.
- **Glyphs and schemes (single source):** `dictionary_app/utils/constants.py` defines every emoji and URL scheme used across the apps — `ARROW_MARKER` (`👉`), `CROSS_MARKER` (`❌`), `BACK_ARROW` (`⬅️`), `FORWARD_ARROW` (`➡️`), `CHECK_MARK` (`✅`), `CHECK_BLANK` (`⬜`), `RADIO_ON` (`🟢`), `RADIO_OFF` (`⚪`), `GEAR_MARKER` (`⚙️`), `MAGNIFIER_MARKER` (`🔍`), `BOOKS_MARKER` (`📚`), `COLLAPSED_TRIANGLE_ENTITY`/`EXPANDED_TRIANGLE_ENTITY` (`▶`/`▼`), and `SCHEME_WORD/SOURCE/PREVIEW/TOGGLE_SECTION`. Import the constant everywhere the glyph is needed. The arrow is used in the entry view (`headword-arrow`/`sense-arrow`, entry_formatter.py) and injected by the sources panel renderer (`build_filtered_html`, which imports `ARROW_MARKER` internally — the renderer receives only the target anchor id); the nav bar uses `BACK_ARROW`/`FORWARD_ARROW` (entry_viewer.py); the nav-bar close and sources-search close buttons use `CROSS_MARKER`. Markup-only glyphs live in `markup_app/utils/constants.py` (see `AGENTS_markup.md`). Never re-type any of these emoji/entity/scheme strings in widget code.
- **Tag attributes (single source):** `dictionary_app/utils/xml_schema.py` is the single registry of dictionary tag attributes — `ATTRIBUTES` (tag → ordered `(name, kind)`; `kind` = `TEXT`/`BOOL`), the `ATTR_*` name constants (`ATTR_ID`/`ATTR_HW`/`ATTR_ENTRY`/`ATTR_EXCL`/`ATTR_N`/`ATTR_LANG`/`ATTR_CODE`/`ATTR_SYN`), and helpers `attribute_names(tag)` / `is_boolean(tag, name)` / `unknown_attributes(root)`. Every read of an attribute across the app (entry/highlight formatters, `dictionary_app/utils/content_rules`, markup broken-links, DB build/search, markup source cache) imports the constants from here instead of re-typing the literal; the markup attribute-completion prompt reads `ATTRIBUTES` from the same module, so adding an attribute once updates code reads AND the prompt together. `sources.xml` (`section/@id`) is a separate document shape and is intentionally NOT in this registry.
- **Arrow-suppression for homonyms (HEADWORD arrow must NOT appear when opening a homonym whose number is a separate `<entry>`):** the decision of whether the opened headword is the *main* headword MUST compare against the full `<hw>` text via `SearchEngine.get_main_headword` (which uses `''.join(hw.itertext()).strip()`, accent-stripped by the caller), NEVER `hw.text` — `hw.text` alone drops an embedded `<n>` homonym numeral ("ґен " + "І") and makes the homonym wrongly look like a sub-headword, triggering the 👉 arrows. This rule applies in ALL navigation paths: entry-list click (`search_results_list.py`), see/word/nav links (`open_entry_by_headword` in `dictionary_app/main_window.py`), and preview-link clicks (`preview:` handler in `dictionary_app/main_window.py`). Sub-headword targets (e.g. a nested `<hw>` like `ґалера абразоў`) legitimately still get the arrow. **See-link path is NOT an exception:** a word/see link (`open_entry_by_headword(..., from_word_link=True)` from the `word:` handler in `on_link_clicked`) that opens an entry whose target IS the main `<hw>` shows NO 👉 next to it, exactly like list clicks, preview clicks, and the nav bar — the former see-link branch that pointed at the main `<hw>` was removed, and the sub-headword target branch applies only when the highlight word differs from the main headword. The comparison main does NOT skip `excl` headwords (see `<hw excl="true">`) — an `excl` headword first in document order makes the real listed headword a "sub" for the comparison, so it points (as in the `ёсьцяка` entry).
- **Italics rule:** `.g`/`.ex`/`.i` glosses are italic, but a nested `<hw>` inside a gloss (a "see" headword, e.g. `один <hw>ґалёш</hw>` in `ґалёшы`) and any inserted `👉` arrow stay **non-italic** — enforced by `font-style: normal` on `.hw`, `.headword-arrow`, and `.sense-arrow` (dictionary_app/theme/widget_styles.py).

### Source Mapping (`SourceMapper`)
- Singleton (`__new__`), loads `dictionary_app/data/source_mappings.json`, builds a variant→abbreviation map (`_variant_to_abbr`). Every mapping currently lists exactly ONE (default) variant — the file was normalized so `variants[0]` IS the canonical form; keep new mappings single-variant too.
- **Space-prefix rule (preserve):** six abbreviations (`акр.`, `п.`, `пав.`, `р.`, `с.`, `вол.`) are in `_space_prefixed_only` and only match when preceded by a space or at position 0. This prevents false matches inside words (e.g. not matching `«п.»` inside `«ап.»`). Do NOT remove or generalize this whitelist.
- `get_abbreviation(text)`: exact match first, then longest-variant-first fallback.
- `extract_abbreviations(text)`: uses a compiled combined regex and returns `(abbr, variant)` pairs; same space-prefix check applies. Single-letter variants (currently only `С`) additionally require word boundaries: they do not match when adjacent to a letter on either side, so `С` still links standalone (`<src>С</src>`, `С.`) but not inside `Старадуб`/`Старина`.

### Window Layout (`MainWindow.setup_ui`)
- Vertical main layout: top row (search box [stretch 1] + insert-ґ button + sources button + settings button), bottom row (results list + splitter)
- Bottom row is `QHBoxLayout` (not a splitter): results list at stretch 0 (fixed 150px) + `bottom_splitter` at stretch 1
- `bottom_splitter` (`QSplitter` Horizontal) holds: entry viewer (initial `SPLITTER_ENTRY_INITIAL`=400px) + sources viewer (initial `SPLITTER_SOURCES_INITIAL`=400px)
- Both splitter panes are non-collapsible (`setCollapsible(0/1, False)`)
- Window default: 765x650px, minimum width dynamically computed as sum of visible panel minimums
- `_update_min_width()` recalculates on every show/hide of results list or sources panel
- Global stylesheet applied via `QApplication.instance().setStyleSheet(GLOBAL_STYLE)`; the results list uses `RESULTS_LIST_STYLE` (both in dictionary_app/theme/widget_styles.py)

### Entry Viewer (`EntryViewer`)
- `DictTextBrowser` (QTextBrowser subclass) inside a QVBoxLayout with `NavigationBar` above it
- Read-only, no external links (`setOpenExternalLinks(False)`), `ClickFocus` policy
- Document margin: 15px left/right (`DOCUMENT_MARGIN`) via `rootFrame().frameFormat()` — **re-applied on every `setHtml`** because Qt resets the root frame format when HTML is set.
- `ENTRY_STYLESHEET` set as document default stylesheet for HTML rendering
- `stored_html` holds the last displayed HTML for refresh/restore
- `ScrollManager` handles anchor scroll, resize re-scroll, and cached state restore
- `setSource` overridden to block navigation for `word:`, `source:`, `preview:` schemes (checked against `SCHEME_WORD`/`SCHEME_SOURCE`/`SCHEME_PREVIEW` in `dictionary_app/utils/constants.py`)

### Navigation Bar (`NavigationBar`)
- Fixed height 30px (`BAR_HEIGHT`), horizontal layout: Back | Back-spacer | Flex-spacer | Forward | stretch | Close
- Back/Forward buttons: 95px wide each (`NAV_BUTTON_WIDTH`), emoji labels (`BACK_ARROW`/`FORWARD_ARROW` + `strings.nav.back/forward`), flat transparent style
- Close button: `IconButton`, 30x30px (`BUTTON_SIZE`)
- Visible only when `navigation_stack` has >1 entry
- Back button hidden when at index 0 (replaced by fixed-width invisible spacer to keep layout stable)
- History stack entries carry `{headword, sense_parts, entry_row_id, target}`; `push()` truncates forward history on new push — see Navigation History for the full identity/dedup rules
- The preview sentinel `_PREVIEW_SENTINEL` (`'__preview__'`, a module constant in `dictionary_app/main_window.py`) is used as a headword -- intercepted in `open_entry_by_headword` to restore preview

### Results List (`SearchResultsList`)
- Uses `QListView` + `ResultsListModel` (a `QAbstractListModel` in `dictionary_app/panels/search_results_list.py`) so the widget renders only visible rows instead of materializing one `QListWidgetItem` per row (matters at full-dictionary scale; the model is the single source of rows).
- Fixed width (`RESULTS_MIN_WIDTH` = 150px), horizontal scrollbar always off
- No focus policy on the view -- keyboard nav (Up/Down/Enter) routed via `SearchBox` signals; `ElidingDelegate` lives in `dictionary_app/widgets/result_list_helpers.py` (shared with markup, which still uses `QListWidget` + `select_row`/`navigate_rows`); the shared `clamped_row(current, direction, count)` computes a nav target row (or `None` when out of range / empty list) and is used by both `navigate_rows` and `SearchResultsList.navigate`; this app does model-`QModelIndex` equivalents in `SearchResultsList` (`_select_row`/`navigate`/`current_item`)
- Custom `ElidingDelegate`: index-based `initStyleOption` elides text exceeding `viewport().width() - RESULTS_ITEM_PADDING`px using `Qt.ElideRight` — works unchanged with the model
- Tooltip shown only for rows that overflow (text wider than viewport); returned via `Qt.ToolTipRole` from the model (the delegate's `helpEvent` shows it, same mechanism as `QListWidgetItem.setToolTip`)
- **Tooltip width calculation must mirror the delegate's paint-time ellipsis decision, but at population time the viewport may not yet reflect the scrollbar.** So: `vw = viewport().width()` (stale width, still frame-aware) minus `verticalScrollBar().sizeHint().width()` ONLY when the list needs a scrollbar, minus `RESULTS_ITEM_PADDING`. Whether it needs a scrollbar is computed deterministically from `sizeHintForRow(0) * row_count > viewport().height()` (NOT `isVisible()`, which is stale pre-layout). This yields the correct tooltip per case — e.g. галоўны ґазавод (128px advance): scrollbar present → threshold 124 → tooltip shown; no scrollbar → threshold 136 → fits, no tooltip. Guard the equality edge: a threshold that lands exactly on the text advance (strict `>`) silently drops the tooltip.
- Tooltip text = `remove_accents(raw_headword)` -- accent-stripped headword
- Font: Cambria/Times New Roman serif, 12pt bold (via `GLOBAL_STYLE`, which now also covers `QListView`)
- Item CSS in `RESULTS_LIST_STYLE` (selector `QListView::item`): left border 3px solid transparent (idle), grey on hover (`#c0c0c0`), blue on selected (`#7c9ec0`); background white -> `#fafafa` hover -> `#edf7fd` selected; text always black
- Model data roles: `DisplayRole` = accent-stripped headword, `UserRole` = entry_link, `UserRole+1` = raw headword, `ToolTipRole` = tooltip or `None`
- First item auto-selected after `display_results` (via `QItemSelectionModel.ClearAndSelect` on `model.index(0, 0)`)
- `display_results()` also clears entry viewer and scroll cache

### Search Box (`SearchBox`)
- `QLineEdit` subclass, fixed height 30px (`SEARCH_BOX_HEIGHT`)
- Signals: `navigate_up` (Up arrow), `navigate_down` (Down arrow), `activate` (Enter/Return)
- Style: white bg, 1px `#c0c0c0` border, 3px radius, 2px padding

### Settings Button (`SettingsButton`)
- Emoji gear icon (`GEAR_MARKER`), 30x30px (`BUTTON_SIZE`), subclass of the shared `MenuButton` base (so size/cursor/`class="menu-button"`/style come from one place), opens `QMenu` on click
- Menu structure: heading -> separator -> `_belarusian_radio` "Belarusian" (with sub-options) -> `_russian_radio` "Russian"
- Built from a `_ToggleOption` base with `_RadioOption` and `_CheckOption` subclasses; radios use `RADIO_ON` (green circle) / `RADIO_OFF` (white circle) glyphs; sub-options use `CHECK_MARK`/`CHECK_BLANK` glyphs, indented 24px left margin, and are inserted BEFORE the russian radio in the menu (`_add_scope_option` + `_scope_actions`)
- Sub-options (Belarusian): at least one must remain checked — `_sync_sub_options` disables the only-checked one (via `_CheckOption.set_active`, which applies `COLOR_DISABLED_FG`)
- `_headwords_option()` / `_examples_option()` return the two sub-options; `_update_sub_visibility` hides/shows them when the russian radio is active
- `get_option_states()` returns the three search options dict (see Search Modes for the exact state mapping)

### Insert Letter G Button (`InsertLetterGButton`, `dictionary_app/widgets/insert_letter_g.py`)
- Momentary `QPushButton` labelled `ґ` (`INSERT_LETTER_G` = `'\u0491'`), subclassing the shared `MenuButton` base (`class="menu-button"` property + `MENU_BUTTON_STYLE`, fixed `BUTTON_SIZE`) so the letter renders at the same 12pt size as the emoji buttons.
- `setFocusPolicy(Qt.NoFocus)` so a click never steals the cursor from a search bar — this is what enables insert-at-cursor behavior.
- Placed in the top row between the search box and the sources button (see Window Layout). `_insert_letter_g` (in `MainWindow`) inserts `INSERT_LETTER_G` at the cursor of whichever `SearchBox` currently has focus (`QApplication.focusWidget()` — the main bar or the sources search line; `QLineEdit.insert` replaces any selection); if no `SearchBox` is focused, it focuses the main search box first, then inserts.

### Sources Panel (`SourcesPanel`)
- `DictTextBrowser` (read-only) + search `QLineEdit` + magnifier `IconButton` (`MAGNIFIER_MARKER`) + close `IconButton` (`CROSS_MARKER`), in a VBox layout; `get_widget()` returns the container
- **Scrollbar-aware floating magnifier (preserve):** the magnifier overlays the viewer top-right in the same 2-column `QGridLayout` (the viewer spans both columns; column 1 is a spacer). `_update_floating_button_inset` sets column 1's minimum width to `overlay_right_inset(...)` (see Scroll Bar Utility) on every `viewer.verticalScrollBar().rangeChanged`, so the button clears the vertical scrollbar when present and sits flush right otherwise.
- Toggle button (`SourcesButton`): book emoji (`BOOKS_MARKER`), subclass of the shared `MenuButton` base (30x30px, `class="menu-button"`, `MENU_BUTTON_STYLE`)
- Loaded from `dictionary_app/data/sources.xml`; HTML built by `sources_renderer.build_filtered_html` (module functions: `build_filtered_html`, `section_matches`, `_element_to_html`)
- Search box filters/sections by text match; a search matching no section renders `strings.nav.no_results`
- When `sources.xml` contains no `<entry>` children, the panel content is `'<body></body>'` (an empty page; no message string is used)
- Panel shown/hidden via toggle button; visibility tracked in `sources_visible`
- **Collapse/search state machine (preserve):** `_collapsed_sections` (a set) tracks collapsed `<section>` ids. Search **auto-expands** collapsed sections that match; on clearing the search, the pre-search collapsed state is restored. Hiding the panel resets all collapsed state and the anchor.
- Section toggle links use the `SCHEME_TOGGLE_SECTION` scheme (`toggle-section:{id}`), rendered by `sources_renderer` with `COLLAPSED_TRIANGLE_ENTITY`/`EXPANDED_TRIANGLE_ENTITY`; the arrow headword marker (`ARROW_MARKER`) is imported inside `sources_renderer` and injected after the anchor span whose id was passed in as `marker_anchor`
- `scroll_to_source(abbr)`: strips trailing `:`/`.` from the abbreviation for anchor lookup, auto-expands collapsed sections containing the target, calls `QApplication.processEvents()` before scrolling so layout is computed.
- `SourcesToggle` (dictionary_app/panels/sources_toggle.py) resizes the splitter (half entry / half sources) on show; on hide it combines entry+sources width back.

### Scroll Manager (`ScrollManager`, `dictionary_app/utils/scroll_manager.py`)
- `scroll_to_anchor(anchor)`: calls `viewer.scrollToAnchor(anchor)` and records `last_anchor`
- `handle_resize()`: re-scrolls to `last_anchor` if set (no debounce timers)
- `cache_scroll()`: saves only the scrollbar value (a plain integer)
- `restore_content(html)`: set HTML and restore the saved scroll value
- `clear_cache()`: clears the cached scroll value and `last_anchor`
- `last_anchor` is cleared to `None` after every `display_entry` and `clear_cache`.

### Scroll Bar Utility (`dictionary_app/utils/scroll_bar_utility.py`)
- `scrollbar_extent(scroll_area)`: vertical scrollbar thickness via `verticalScrollBar().sizeHint().width()` (do NOT use `style().pixelMetric(PM_ScrollBarExtent)` — it crashes on the stylesheet-proxied text edits).
- `vertical_scrollbar_shown(scroll_area)`: predicts presence from `verticalScrollBar().maximum() > 0`, never `isVisible()` (which lags the layout step that emits `rangeChanged`).
- `overlay_right_inset(container, scroll_area)`: right inset for a top-right overlay button = `container.width() - scroll_area.mapTo(container, ...).x() + scroll_area.frameWidth() + scrollbar_extent(scroll_area)`; `0` when the scrollbar is hidden. Covers any frame/pane between `container` and the scroll area (e.g. the markup tab pane), so the button's right edge meets the scrollbar's left edge.

### Link Routing (`on_link_clicked` + `open_entry_by_headword`)
- URL schemes (`SCHEME_WORD`/`SCHEME_SOURCE`/`SCHEME_PREVIEW` in `dictionary_app/utils/constants.py`): `word:`, `source:`, `preview:`. All routed through `LinkHandler.process_url` / `on_link_clicked` (see Entry Viewer for `setSource` blocking). `process_url` returns `(link_type, target, sense_parts, target_hw)`, where `target_hw` is the fourth element only for entry-scoped `word:E|H` links.
- **Word-URL forms:** `word:H` (whole-entry target, H = entry XML ID or headword text), `word:E|TEXT` / `word:E|H` (scoped: open entry E, then target TEXT/H *within that entry only*), `word:H n, m` (sense parts). **There is no `E#H` form** — the old `#` fragment scheme is fully removed from formatter, link handler, DB, and markup; do not reintroduce it.
- **`word:` links with `|` are built as raw `|` in the href, but Qt percent-encodes `|` to `%7C` in the delivered `QUrl`.** `LinkHandler.process_url` MUST `unquote()` before splitting on `|`, otherwise the target arrives as `E%7CH` and the entry lookup fails.
- **`<see>` target forms (see Source Data State for counts):**
  - `<see>TEXT</see>` → `word:TEXT` (plain whole-entry link)
  - `<see hw="H">TEXT</see>` → `word:H` (bare whole-entry link; the `hw` value is the target, the text is only the label)
  - `<see entry="E">TEXT</see>` → `word:E|TEXT`
  - `<see entry="E" hw="H">TEXT</see>` → `word:E|H`
- **`<see>` text resolution (`SearchEngine.get_entry_by_headword`) is EXACT — case- and space-preserving:** SQL equality on `normalized_headword`/`normalized_plain_headword` (spaces preserved at build time, `build_database.py`) across BOTH the `dictionary` and `sub_headwords` tables (so a `<see>` may target a sub-headword), followed by exact `remove_accents(matched_text) == remove_accents(target)`; the first candidate whose de-accented text matches with the SAME case wins (a case-distinct headword such as `Юр` vs `юр` is never conflated). `collapse_spaces=True` appears only in the search-box LIKE narrowing (`_like_pattern`); the final regex filter uses `\s+`, so distinct multi-word headwords are never conflated. The click path never applies `normalize_jo_to_je` (targets keep `ё` — that normalization stays limited to t-tag indexing/search, see Accent-Handling Chain), and `remove_accents` never touches `ў` (U+045E), so `<see>ў</see>` ↔ `<hw>ў</hw>` resolves — but only in its precomposed form (у + combining U+0306 is neither stripped nor recognized).
- **Scoped target resolution is entry-local:** `SearchEngine.get_entry_sub_headword(entry_row_id, target)` only ever looks inside the resolved entry's own sub-headwords, so a homonym with the same headword in another entry can never be picked up. It matches `<hw id>` exactly first, then de-accented sub-headword text **CASE-EXACTLY** (`Юрка` and `юрка` are distinct — a target whose exact case has no sub-headword also returns `(None, None)`); an **ambiguous text match (more than one)** returns `(None, None)` and the author must use the explicit `hw` attribute. A dead `hw` value degrades to the text target when it is unique.
- **`<see>` with a homonym `<n>`**: the target string is built from the whole `<see>` content (`itertext`, which includes an embedded `<n>` numeral), so `<see>грыжа <n>ІІ</n>, 1, 2</see>` renders the full `грыжа ІІ, 1, 2` as a `word:` link to headword `грыжа ІІ` with sense parts `[1, 2]`. `LinkHandler.parse_link_text` is token-based: it detaches a *trailing* sense list (digit or single-letter tokens) from the word, and any trailing Roman-numeral token after the word (Cyrillic `І`/`і` or Latin `I`/`i`, `V`, `X`) stays on the word as the homonym marker. `get_entry_by_headword` falls back to comparing accent-stripped *display* headwords when the stripped normalized index has no match — required because homonyms are indexed n-stripped (`грыжа ІІ` → `грыжа`).
- **Preview links** (`preview:{entry_id}|{anchor}`): URL-decode the anchor if it contains `%`, look up the result in `current_results` first then fall back to `SearchEngine.get_entry_by_id(entry_id)`, set `_highlight_entry = True`, save `_last_preview_html`, and push the headword onto the nav stack with `_PREVIEW_SENTINEL` as the older entry (Back returns to the previews).
- **`_PREVIEW_SENTINEL`** (`'__preview__'`): `open_entry_by_headword` intercepts `headword == _PREVIEW_SENTINEL` and calls `_restore_preview()` (restores `_last_preview_html`, clears display state and nav bar). Preserve this sentinel and set `_highlight_entry = True` whenever a preview link is followed. The nav-bar clear is INTENDED, not a bug: previews are not an entry, so they terminate the entry-history chain — Back/Forward never spans a preview page, and the bar hides and the stack resets the moment previews are shown.
- `open_entry_by_headword(headword, sense_parts=None, target_hw=None, entry_row_id=None, from_navigation=False, from_word_link=False)`:
  - `_PREVIEW_SENTINEL` → restore preview and return.
  - Resolves the entry: by `entry_row_id`, else by headword (searches `current_results` exact, then accent-stripped, then the DB, then `SearchEngine.get_entry_by_xml_id` for `from_word_link`). Parses the resolved entry via `get_parsed_entry` (shared cache via `get_main_headword`).
  - **Resolves the entry FIRST, then the target inside it** when `target_hw` is set: `get_entry_sub_headword(resolved_entry_row_id, target_hw)` supplies the highlight word and the local anchor. Never resolve the target against the whole corpus.
  - Sets format target: `set_target_senses(sense_parts, headword)` if sense_parts given; else `set_target_subheadword` if the resolved highlight word is non-empty and differs from the main headword; else `clear_target()`. There is no separate `from_word_link` branch: a see/word link resolving to the entry's own main `<hw>` falls through to `clear_target()` and renders WITHOUT the pointing finger, same as every other navigation path (see Arrow-suppression for homonyms).
  - Tracks the currently displayed state in `current_display_row_id` / `current_display_headword` / `current_display_senses` / `current_display_target` (see Navigation History below); these are reset on previews, search, close, and unresolved targets.
  - Pushes to nav stack only when NOT `from_navigation` and the **full navigation identity** changed — headword, entry row, applied sub-headword target, or sense list (see Navigation History). If the previous headword was None but `_last_preview_html` exists, pushes `_PREVIEW_SENTINEL` as the older entry.
  - **Unresolved target:** when the headword/link resolves to nothing (e.g. a `<see>` to a word absent from the dictionary), the navigation is NOT a no-op — it becomes an explicit EMPTY step: pushes the target on the nav stack (same old-headword/`_PREVIEW_SENTINEL` rules) and displays an empty `<body></body>` window. This keeps Back/Forward in increments (empty → previous entry → … → preview) in every search mode.
  - Scrolls to the appropriate anchor (`sense_{n}`, the entry-local sub-headword anchor, or the headword).

### Navigation History (`NavigationBar.push` + display state)
- **The navigation identity is `(headword, entry_row_id, sub-headword target, sense_parts)`.** All four participate in the dedup check; sense links and scoped sub-headword links therefore create a real history step even when the entry itself does not change. A repeated click on the identical state is a no-op.
- `push(headword, sense_parts, old_headword, entry_row_id=None, old_row_id=None, target=None, old_target=None, old_senses=None)`.
- The stack tip must be the entry actually being left. It can be stale, because opening an entry from the search results calls `display_entry()` directly and never runs `push()` — and the list click has already cleared the stack (`navigation_bar.clear()` in `_present_clicked`), so the leaving state is seeded fresh; when the tip disagrees on headword, row, **or senses**, the leaving state is re-appended before the new one.
- `old_target`/`old_senses` must come from the `current_display_*` fields, **not** from `formatter.get_target_subheadword()` — `format_entry` clears the `FormatContext` after every render, so the formatter can no longer report what was actually applied. The same applies to the combined-mode preview push in `on_result_clicked`: it passes the NEW `applied_target` as `target` and the pre-click `old_target` as `old_target`, with `_PREVIEW_SENTINEL` as the leaving headword.
- **Back/Forward restore the recorded target verbatim.** `target_headword` is `remove_accents(headword)`, so re-deriving a target from a recorded headword would silently re-apply a target that was recorded as `None` (that headword may itself be a sub-headword of the entry). Target derivation from the headword therefore runs only when `from_navigation` is False; the navigation callback (`on_nav_open`, the only `from_navigation=True` caller) uses `target_subheadword`/`sense_parts` from the stack entry as-is.
- Unresolved targets are explicit empty steps (see Link Routing), so Back/Forward stay in increments.
- `same_senses(a, b)` (`dictionary_app/panels/entry_viewer.py`, re-exported from `dictionary_app.panels`) normalizes `None`/`[]` to the same empty sense list; use it for every sense comparison.

### Highlighting
- Entry opened from preview -> search terms highlighted with `#FFF9C4` background (`COLOR_HIGHLIGHT_BG` in dictionary_app/theme/widget_styles.py)
- Same-entry see links preserve highlight (`_highlighted_entry_id` matches); different-entry see links clear it
- Close button on navigation bar -> `_dismiss_highlight()` re-renders without highlight
- Highlight applied via `SearchEngine.apply_highlight` — the excluded classes match the Exclusion Rules table (enforced by `_should_exclude_from_highlight`):
  - protects `<a>` tags and excluded class blocks via `_protect_class_blocks` (manually tracks `<span>` nesting depth to find the matching close)
  - **preview mechanism:** excluded children are wrapped in `<span class="search-excluded">` and passed as `exclude_classes=[_EXCLUDED_HIGHLIGHT_CLASS]`; protected blocks become `\x00A{idx}\x00` placeholders, so the regex only ever scans the highlightable (indexed-equivalent) text — excluded fragments are rendered but never highlighted
  - text parts containing a placeholder are sub-split on `(\x00[^\x00]*\x00)` so a protected block never merges adjacent plain text into one skipped part
  - runs `finditer` across concatenated text parts, maps highlights back to individual parts, restores placeholders twice (to handle nesting)
- In `MainWindow.display_entry`, the exclude set starts with `hw` **always**. When `_search_normalize` is True (translations-only), `ex` is also excluded. When `_search_in_headwords` is True, `t` is excluded. `<hw>` must NEVER be highlighted in any Belarusian-headword search variant.

### Global Shortcut
- Ctrl+C copies selection from any QTextEdit via `install_global_copy` in `dictionary_app/shortcuts/shortcuts.py`

## Writing Conventions
- No comments in code unless essential
- Module-level constants, no inline literals (use `dictionary_app/theme/layout_constants.py` for metrics, `dictionary_app/utils/constants.py` for glyphs/schemes, `dictionary_app/theme/widget_styles.py` for colors/styles)
- All CSS in `dictionary_app/theme/widget_styles.py` (one source of truth; `RESULTS_LIST_STYLE` included)
- Qt signals for cross-component communication
- Private methods use `_` prefix
- Pane = self-contained UI component (EntryViewer, SourcesPanel, SearchResultsList)
- Window = top-level OS window (MainWindow)
- **Docs must stay de-duplicated**: state each fact in exactly ONE place; where a later section would repeat it, use a `see <section>` cross-reference instead of restating it. Restating creates drift when code changes and only one copy gets updated.
- **`dictionary_app/localization/strings.json` (dictionary app) and `markup_app/localization/strings.json` (markup app) are manually maintained by the user — NEVER rewrite them wholesale, re-serialize, or reformat them.** Edit individual keys only, reading the file immediately before each edit and preserving all existing content (including indentation quirks). Overwriting user edits is strictly forbidden.

## Database Schema
- `dictionary` table: `(id INTEGER PRIMARY KEY, headword, sort_headword, normalized_headword, normalized_plain_headword, full_entry, entry_link, source_file, hw_xml_id)` — `hw_xml_id` holds the entry's own `<hw id>` (6 populated), used by `get_entry_by_xml_id` for `word:` and markup lookups
- `sub_headwords.link` holds the **owning entry's XML ID**, not a `E#H` compound; `<hw id>` values live in `sub_headwords.hw_xml_id`
- `sub_headwords` table: `(id, headword, sort_headword, normalized_headword, normalized_plain_headword, main_entry_id)` — sub-headwords share parent entry
- `content_index` table: `(id, entry_id, tag_type, searchable_text)` — pre-built index for translation/examples search
- FTS5 trigram virtual tables: `headword_fts(word, dict_id UNINDEXED, sub_id UNINDEXED)` (populated from both headword tables' `normalized_headword`) and `content_fts_t`/`content_fts_ex` (populated from `content_index` by `tag_type`) — see Content Index and Scale Notes
- `source_file` column tracks which file in `dictionary_app/data/dictionary/` each entry came from (used by markup app for save)
- **Indexed today:** `content_index(tag_type, searchable_text)`, `content_index(entry_id)`, `dictionary(normalized_headword)`, `dictionary(normalized_plain_headword)`, `sub_headwords(normalized_headword)`, `sub_headwords(normalized_plain_headword)`. `dictionary.entry_link` is NOT indexed, so `entry_link` lookups are full scans — fine at the current corpus (see Scale Notes). `get_entry_by_link` consults `dictionary.entry_link` first, then falls back to `sub_headwords.link` (returning the sub-headword's display headword with the parent's `full_entry`) — a dead `entry_link` never fails if it lives on the sub-headword.

## Build / Rebuild
- Entry points: `dictionary_app/run.py` (dictionary app) and `markup_app/run_markup.py` (markup app) each insert the project root on `sys.path`, construct `QApplication` first, then the respective window with `create_search_engine()` from `dictionary_app.db.bootstrap`.
- `create_search_engine()`: calls `stale_source_files()` to find which sources need rebuilding — the whole set if the DB is missing, else any entry of `dictionary_app/data/sources.xml` or a `*.xml` file in `dictionary_app/data/dictionary/` whose mtime is newer than the DB (non-XML artifacts such as `.txt`/docs are ignored). If any are stale it calls `build_database(stale_files)` — which rebuilds ONLY those files — then returns `SearchEngine(db_path)`.
- `build_database(file_names=None)`: with no argument, or if the DB file doesn't exist, it does a FULL rebuild (drops/recreates the tables — `dictionary`, `sub_headwords`, `content_index`, plus their indexes and the three FTS5 virtual tables — and re-inserts every `*.xml` file in sorted order plus `sources.xml`). Otherwise it rebuilds incrementally: for each named source file it DELETEs that file's rows from `dictionary`/`sub_headwords`/`content_index` matched by `source_file`, then re-inserts from the XML. Every build ends by re-populating the FTS5 tables wholesale (`DELETE FROM` + `INSERT … SELECT` from `content_index` and the headword tables). It reuses the existing DB file (never `os.remove`-s it) so a second process holding the DB open does not block a rebuild on Windows. `get_source_path(source_file)` maps a `source_file` (e.g. `'sources.xml'` or a split file name) to its absolute path; both apps use it instead of re-deriving paths.
- At build time the SAME exclusion rules as the search engine are used when building `content_index` (see Exclusion Rules). Translation index text is normalized with `normalize_jo(remove_accents(...))`; example index with `remove_accents(...)` only (no ё→е).
- `normalized_headword = remove_accents(sort_headword).lower()` at build time — i.e. computed from the n-stripped headword, so embedded `<n>` homonym numbers are NOT searchable/indexable (typing `І` matches nothing; `ґен` still matches `ґен І`/`ґен ІІ`). The regex re-filter in `_search_headwords` matches the accent-stripped, case-PRESERVING display headword (`remove_accents(r[1])`) — the regex built by `compile_search_regex` is case-sensitive per letter (lowercase `ю` → `[юЮ]` matches both cases; uppercase `Ю` → matches only `Ю`), so an uppercase query finds only uppercase headwords while a lowercase query finds both (`Юда́ш` vs `юда́шыць` are distinct rows).
- `sort_headword` = headword text with embedded `<n>` homonym content removed (`hw_text_excluding_n`), used for the entry-list ordering and as the search-discriminated text; the `headword` column keeps the full text (homonym numbers displayed).

## Performance / Scale Notes
Measured at the current corpus (295 dictionary rows + 172 sub-headword rows across 15 source files; full build ~31 ms):
- Already scale-safe: trigram FTS5 for headword (`headword_fts`) and content (`content_fts_t`/`content_fts_ex`) search, list rows that carry `NULL` instead of `full_entry` (`full_entry` is fetched by `id` only when an entry is parsed), indexes on the normalized-headword columns, LRU `_parsed_cache` (≤ `_PARSED_CACHE_MAX_SIZE` = 512) and LRU `_preview_cache` (`_PREVIEW_CACHE_MAX_SIZE` = 2048, keyed by `(entry_id, headword, tag, pattern)`), virtualized `QListView` + `ResultsListModel` (only visible rows rendered; tooltips computed in the model's `data()`), and per-file incremental rebuild.
- Projected AT ~300k headwords with today's code: headword and content searches go through trigram FTS whenever the query's longest alphanumeric span is ≥3 chars (fast), degrading to a `LIKE '%…%'` scan over `content_index`/headword columns only for short (1–2 char) spans; empty/all-results list rows are lightweight (no `full_entry`); per-click headword lookup is an indexed hit while `entry_link` lookup still scans.

Remaining 300k-scale work (the FTS, index, and list-query items are done):
- Build previews lazily (on click / for visible rows only) instead of parsing the candidate set on every keystroke — the `_preview_cache` LRU only serves identical repeat queries, not fresh keystrokes.
- Make short (1–2 char) query spans fast — they still fall back to `LIKE '%…%'`, which a B-tree index cannot serve.
- The one synchronous slow build is the FIRST run when the DB is missing (full path; ~40–60 s at 300k entries). If that ever matters, ship a prebuilt DB or build in the background; per-edit rebuilds are always incremental.

## Key UI Wiring to Preserve
- **Settings button `_consume_next_press`**: after the menu closes (`aboutToHide`), if the cursor is still over the button, `_consume_next_press` is set so the mousePressEvent consumes the release and the menu does NOT immediately re-open. Keep this workaround.
- **`show_all_entries()` first-show guard**: runs on the FIRST `showEvent` only (guarded by `_initial_shown` via `getattr`), so the initial entry load happens after the window is visible. Both the dictionary app and markup app use this.
- **`SearchResultsList.on_clicked`** resolves the clicked `QModelIndex` (index-based `clicked` signal) by its accent-stripped headword (model `DisplayRole`), computes `<hw>` equality via `SearchEngine.get_main_headword` (which does NOT skip `excl`), sets `set_target_subheadword` when the clicked headword differs from the main headword, then `display_entry` + scroll; otherwise `clear_target()`. It then calls `self.navigation_bar.clear()` and **only afterwards** returns the applied target (the sub-headword, or `None`) so `MainWindow.on_result_clicked` can store it in `current_display_target` for nav-identity comparison (see Navigation History). The `clear()` must stay BEFORE the `return` — it was once left after it and became unreachable, silently keeping stale Back/Forward history across list clicks.
- **Result-click state writes in `on_result_clicked`**: it captures `old_target`/`old_senses` from the display state before the click, stores `current_display_target = applied_target`, then unconditionally resets `current_display_senses = None`. A click that fails to materialize (`on_clicked` early-returns `None` — e.g. a list row whose entry was deleted from the DB while the list was live) therefore clobbers `current_display_target` to `None` while the previous entry stays on screen; the next `push()` gets a wrong `old_target`/`old_senses`. Known edge; requires a stale DB row to trigger.
- **Combined-mode result click**: when clicking a headword match while `_last_preview_html` exists, `_PREVIEW_SENTINEL` is pushed onto the nav stack so Back returns to the previews.