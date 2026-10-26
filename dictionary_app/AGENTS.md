# Stankievichau Slounik — Architecture Guide

Two applications share code: the **dictionary app** (`dictionary_app/`, which
also holds every shared module) and the **markup app** (`markup_app/`, which
imports shared code from it). This file is the shared + dictionary architecture
guide; it sits in `dictionary_app/` alongside the shared modules, and the markup
app has its own guide.

- `markup_app/AGENTS.md` — markup app architecture (editor, save flow, link
  markers, completion, broken-link filters).
- `markup_app/data/MARKUP_PATTERNS.md` — raw OCR → XML markup conventions.
- `tools/DEVELOPMENT_PRACTICES.md` — workflow, tooling (including every script in
  `tools/`), environment, code standards, end-of-cycle cleanup checklist.

Do not restate those files here; cross-reference them.

# Dictionary App

## Goal

A Belarusian–Russian bilingual dictionary. Queries search headwords
(Belarusian), translations (Russian `<t>`), or examples (`<ex>`), with
tab-separated search modes and a split-pane UI. The markup app
(`markup_app/AGENTS.md`) edits entries and saves them back to the source XML.

## Project Layout

```
stankievichau_slounik/
├── dictionary_app/          # dictionary app + ALL shared modules
│   ├── AGENTS.md            # shared + dictionary architecture (this file)
│   ├── main_window.py       # window, search/navigation orchestration
│   ├── panels/              # EntryViewer, SearchResultsList, SourcesPanel, SourcesToggle
│   ├── widgets/             # SearchBox, icon/menu buttons, delegates, row-nav helpers
│   ├── db/                  # SearchEngine, build_database, create_search_engine
│   ├── format/              # format_entry, highlight_formatter, link_handler, render_sources, source_mapper
│   ├── utils/               # shared primitives (table below)
│   ├── theme/               # layout_constants.py, styles.py
│   ├── localization/        # load_strings.py + manually maintained strings.json
│   ├── data/                # sources.xml, source_mappings.json, dictionary/dictionary_*.xml
│   ├── build/               # dictionary.db (gitignored)
│   └── run.py               # launcher
├── markup_app/              # entry editor; imports dictionary_app, never the reverse
│   └── AGENTS.md            # markup-only architecture
└── tools/                   # helper scripts + DEVELOPMENT_PRACTICES.md
```

`dictionary_app/utils/` (shared primitives):

| module | contents |
|---|---|
| `remove_accents.py` | `remove_accents` |
| `sort_keys.py` | `alphabet_sort_key`, `entry_id_sort_key`, `encode_order_key` |
| `normalize_headword.py` | `strip_quotes`, `resolve_headword`, `has_keep_acc`, `normalize_jo_to_je` |
| `collapse_duplicates.py` | `collapse_same_entry_duplicates` |
| `compile_search_regex.py` | `compile_search_regex` |
| `extract_content_text.py` | `is_excluded_child`, `content_text`, `hw_text_excluding_n`, `d_hw_variants`, `index_text` |
| `measure_scrollbars.py` | `scrollbar_extent`, `vertical_scrollbar_shown`, `overlay_right_inset` |
| `scroll_state.py` | `ScrollState` |
| `install_global_copy.py` | `install_global_copy` |
| `constants.py` | glyphs + URL schemes (single source) |
| `xml_schema.py` | tag attribute registry (single source) |
| `item_roles.py` | Qt item role constants |

## Key Design Decisions

### Search Modes

- Three boolean options: `search_in_headwords`, `search_in_translations`,
  `search_in_examples`.
- **Exclusive mode**: exactly one of translations/examples ON, headwords OFF —
  preview snippets in the entry pane, results list hidden.
- **Combined mode**: headwords ON + examples ON, translations OFF — headword
  matches fill the results list, example matches fill previews.
- **Any other combination** (or headwords-only) → standard headword search with
  the results list visible.
- Empty main-search results leave the entry pane empty and clear the list. The
  "no results" message (`strings.nav.no_results`, "Няма вынікаў.") is used ONLY
  by `render_sources.build_filtered_html` when a sources search matches nothing.
- **Settings state machine** (`SettingsButton.get_option_states`):
  `_russian_radio` → `{headwords:False, translations:True, examples:False}`;
  `_belarusian_radio` → `{headwords:_headwords_option(), translations:False,
  examples:_examples_option()}` — translations is ALWAYS False for Belarusian;
  the sub-options control headwords + examples only.
- **Combined mode does a dual search**: `on_search` runs TWO `search_engine.search()`
  calls (headwords-only fills the list, examples-only fills previews). Do NOT
  collapse this into one call.
- `SearchEngine.search` raises `ValueError` when translations AND examples are
  requested together; the settings menu never produces that state.
- **Headword search shows duplicate rows by design**: `_HEADWORD_ROWS_SQL` joins
  the `dictionary` and `sub_headwords` selects with `UNION ALL` (not `UNION`), so
  an entry whose sub-headwords include a duplicate of itself appears as multiple
  identical list rows (e.g. `зачапіцца` returns entry 88 twice). Keep it `ALL` —
  the markup duplicate-group filter relies on every row being visible. The
  results LIST collapses same-entry duplicates to one row via
  `collapse_same_entry_duplicates` (key = DB entry id + accent-resolved headword,
  first occurrence wins); genuine homonyms in DIFFERENT entries stay, and the SQL
  is never narrowed. The build enforces the same invariant: `insert_entry` emits
  EVERY non-`excl`, non-main `<hw>` as a `sub_headwords` row with **no dedup**.

### Content Index

- `content_index` table: `(entry_id, tag_type, searchable_text)` + indexes, built
  by `build_database.py` with the same exclusion rules as the search engine.
- Translation/example search first queries the trigram FTS5 indexes
  (`content_fts_t`/`content_fts_ex`, populated from `content_index`) when the
  query's longest alphanumeric span is ≥3 chars (`_TRIGRAM_MIN_SPAN`), else falls
  back to `LIKE '%…%'` over `content_index`; only matching entries are fetched
  and parsed to build previews.
- `SearchEngine.get_parsed_entry(entry_id, xml_string)` parses once and caches the
  root in `_parsed_cache` keyed by `entry_id`; reused by `_annotate_content_matches`,
  `get_main_headword`, and preview-link clicks. It is an LRU
  (`collections.OrderedDict`, `move_to_end`, evicts at
  `_PARSED_CACHE_MAX_SIZE = 512`). Eviction is per entry: a miss reparses the
  supplied `xml_string`, so no bulk clearing is needed.
- `SearchEngine.invalidate_entry(entry_id)` drops that entry from `_parsed_cache`
  (the markup app calls it after a save).
- Preview results are cached in the LRU `_preview_cache`
  (`_PREVIEW_CACHE_MAX_SIZE = 2048`) under
  `(entry_id, headword, keep_acc, tag, pattern)`.
- `SearchEngine.get_main_headword(entry_id, xml_string)` returns the FIRST `<hw>`'s
  full text (`''.join(element.itertext()).strip()`), including an embedded `<n>`
  and an `excl` variant — the canonical main-vs-sub comparison text. It
  deliberately does NOT skip `excl`.
- `SearchEngine.get_main_headword_display(...)` returns the display form (accents
  resolved via `resolve_headword`), used for anchor scrolling and highlight-word
  comparison.
- List queries carry `NULL` instead of the entry XML;
  `SearchEngine.materialize_result(result)` loads the `entry_body` table's `xml`
  column when an entry is actually displayed.

### Exclusion Rules

| Context | Excluded elements |
|---|---|
| Translation (`<t>`) search indexing | `<src>`, `<st>`, `<g>`, `<see>`, `<i lang="vl">`, `<i excl="true">`, `<lang code="vl">`, `<lang code="la">`, `<lang excl="true">` |
| Translation preview highlight | Same as indexing — excluded children rendered but not highlightable |
| Example (`<ex>`) search indexing | `<src>`, `<st>`, `<i lang="ru">`, `<lang code="ru">` |
| Example preview highlight | Same as indexing |
| Headword (`<hw>`) row indexing | `<hw excl="true">` |

The rules live once in `dictionary_app/utils/extract_content_text.py`
(`is_excluded_child`, `content_text`, `index_text`) and are shared by the DB build
and the search engine.

### `<hw excl="true">`

- A `<hw>` carrying `excl` (any value, e.g. `excl="true"`) is excluded from ALL
  index/logic: never a `dictionary` or `sub_headwords` row (so never in the entry
  list, headword search, empty query, or collation; the entry is indexed under its
  first non-excl `<hw>`) and skipped in `d_hw_variants` /
  `_preview_hw_fields`.
- It is STILL rendered (bold, anchor id, comma absorption) and STILL participates
  in the pointing-finger (`👉`) logic — the ONLY logic it stays in:
  `SearchEngine.get_main_headword` does NOT skip it, and `is_target_headword` can
  point at it. In `•<hw excl="true">ёсьць</hw>, <hw>ёсьцяка</hw>` the comparison
  main is `ёсьць`, so clicking the listed `ёсьцяка` row points 👉 at `ёсьцяка`,
  exactly like a sub-headword.
- Data example (`dictionary_Jo.xml`):
  `•<hw excl="true">ёсьць</hw>, <hw>ёсьцяка</hw>,—<i>см. под <see>ё</see>.</i>` —
  a homographic cross-ref variant that must not be indexed (real `ёсьць` stays a
  sub-headword of `ё`) yet stays visible in the headword line.
- Applied at DB build (main row = first non-`excl` `<hw>`, sub-rows skip `excl`),
  preview headword aggregation, and `d_hw_variants`. The finger logic in
  `format/format_entry.py` and `get_main_headword` intentionally do NOT skip them.

### Source Data State

- Ґ-initial entries live in `dictionary_app/data/dictionary/dictionary_G.xml`.
  Authoritative OCR per letter: `markup_app/data/dictionary_raw/dictionary_<letter>_raw.txt`.
  Rebuilds/saves resolve the file via `build_database.get_source_path`.
- Markup conventions (tags, entry shapes, spacing, OCR fixes, homonyms/`link`)
  are documented in `markup_app/data/MARKUP_PATTERNS.md`; this file covers only
  app behavior.
- Every letter file keeps its raw file's print order. On-screen order is
  alphabetical because results are sorted by `collation_key`; file order and list
  order are intentionally different. Do not re-sort the XML files.

### Cross-Reference IDs (`<hw id>` / `<see>`)

- `<entry id="…">` gives an entry a stable XML ID (`dictionary.entry_link`);
  `<hw id="…">` gives a sub-headword its own ID (`sub_headwords.hw_xml_id`).
- `get_entry_by_link` resolves `<entry id>`: `dictionary.entry_link` first, then
  `sub_headwords.link` (which holds the OWNING entry's ID, not a compound).
  `get_entry_by_xml_id` matches `hw_xml_id`.
- A `<see>` may carry `entry=`, `hw=`, both, or neither (see Link Routing).
  Undeclared references that match nothing take the documented text-match or
  dead-link path; they are not build errors.
- A handful of sense links point at words absent from the corpus — pre-existing
  content gaps, not link-handler bugs; they take the unresolved-target empty step.
- `<entry id>` values use the `_p{n}` page suffix convention (e.g.
  `абора_p5_1`); underscores are part of the ID.

### Preview System

- Translation previews: the sense number is prepended as
  `<span class="{num_tag}">` (`num_tag` = the sense's `<n>` tag name, falling
  back to `<b>`), **unless** the matched `<t>` sits in a sub-headword `<d>` nested inside
  the sense (walk `<t>` → `<sense>` crossing a `<d>`): a sub-headword is its own
  entry and must not carry the main sense number. When the matched `<t>` is
  directly preceded by an `<ex>` with `—` tail, the whole `<ex>—<t>` block is
  emitted as `<span class="g">…</span>—` + the `<t>` preview; if that `<ex>` is
  itself preceded by a `<t>` (the `t . ex — t` chain), that `<t>` is leading
  context too. No context from further-back siblings (avoids leaking e.g. a
  `<b>:</b>` separator).
- **Absorbed-`<t>` suppression (translation only):** when a matched `<t>` is
  immediately followed by an `<ex>` (with `—` tail) whose next sibling is another
  matched `<t>`, the earlier `<t>` becomes the later one's leading context and is
  NOT emitted standalone.
- **Sense-number dedup (translation only):** the sense number is prepended at
  most ONCE per enclosing sense across an entry's previews — `highlight` tracks
  emitted sense ids. Both the embedded-`<t>`-in-`<ex>` builder and the plain
  builder share this.
- **Secondary-`<t>` gating (translation only):** after a matched primary `<t>`, a
  trailing `<ex>—<t>` chain is appended ONLY when the secondary `<t>` also matches
  (same `content_text` + `normalize_jo_to_je` as the index); otherwise the whole
  chain is dropped rather than showing unhighlighted gloss context. Leading
  context is NOT gated: an unmatched preceding `<t>` still renders.
- Example previews: trailing `—<t>` appended as `<span class="t">` when the
  pattern is detected.
- Multiple matching elements with the same headword in one entry are **grouped**
  into one preview.
- Results are deduplicated by `entry_id`; a deduped row attaches **all** the
  entry's matches (across every sub-headword) — the surviving headword does not
  filter the preview list.
- Preview spacing: `<br>` between sense previews only when `<br>` exists in the
  raw XML between matched elements (`paragraph_break`); ` <br><br>` between
  headword groups.
- Preview headwords are clickable (`preview:{entry_id}|{headword}`) — opens the
  full entry with highlighting.
- **Preview headword aggregation (`_preview_hw_fields`):** a match inside a `<d>`
  → its ancestor `<d>`'s direct `<hw>` children joined with `|` (plus the n-stripped
  sort variant). Otherwise the entry's `<hw>`s that sit **outside any sense OR
  inside the match's sense** (via `_enclosing_sense`) are joined with `|` (no `<d>`
  in the entry), or the first of those taken (entry has `<d>`s elsewhere but the
  match is outside one) — secondary headwords in OTHER senses are not appended.
  Fallback: the caller's headword. The list renders `|` as `, ` and scrolls to the
  first headword. `<hw excl="true">` is skipped in both paths.
- Each preview is
  `{'headword', 'sort_headword', 'sort_hw_id', 'preview_html', 'paragraph_break'}`;
  `_show_previews` groups by display headword, sorts by `sort_headword`, and
  tie-breaks on `entry_id_sort_key(sort_id)` / `entry_id_sort_key(sort_hw_id)`.

### Search Regex (`compile_search_regex`)

Accent-insensitive, wildcard-aware pattern that re-filters candidates.

- Every literal character accepts optional combining marks U+0300/U+0301; a
  literal carrying a combining accent REQUIRES that accent
  (`_ACCENT_COMB_REQUIRED`).
- Wildcards: `*` → one or more word chars, `?` → one word char, stop at whitespace.
- Word-boundary lookarounds: `(?<![\w\'\u2019\u02BC-])` /
  `(?![\w\'\u2019\u02BC-])` — punctuation is a boundary, apostrophe and hyphen
  are word chars.
- `exact_words=True` (query ends with a space) adds a trailing boundary.
- Multi-word queries: `\s+` between word patterns.
- `ё`↔`е` mapping (`normalize_jo_to_je`) — see Accent-Handling Chain.

### Accent-Handling Chain

`remove_accents` is applied at EVERY layer: SQL `normalized_headword` at build,
query normalization, result-list display text, entry-link matching, and preview
headwords. Never drop it on one layer only.

- **Exception — `keep-acc`:** a `<hw>` tagged `keep-acc` is NOT
  accent-stripped for display or identity. `resolve_headword(text, keep)` returns
  raw `text` when `keep`, else `remove_accents(text)`; `has_keep_acc(attrs_text)`
  tests a raw attribute string; the identity form never converts `ё`→`е`, so
  `<see>ёдка</see>` matches only `<hw>ёдка</hw>`. The flag rides out of the DB as
  the 7th element (index 6) of every result row and must be threaded through
  `display_results`, `_present_clicked`, and the preview cache key.
- `normalize_jo_to_je` (`ё`→`е`, `Ё`→`Е`) is applied **only** for translation
  search (`tag='t'`), never for examples.
- The content-search regex (`_search_via_index`, `t`/`ex`) is built from
  `remove_accents(text.strip())` plus, for `t` only, `normalize_jo_to_je`.
  Candidate narrowing still uses `index_text`/FTS/LIKE; the de-accented regex is
  authoritative, so accented or `ё`-spelled queries still match. (Headwords
  differ — see Wildcard / LIKE building.)
- In `MainWindow.on_search`, `_search_normalize` is True only when
  translations-only (translations ON, examples OFF); `_search_in_headwords`
  mirrors the option. These flags steer highlighting (see Highlighting).

### Wildcard / LIKE building

- Headword search narrows via `headword_fts`/`sub_headword_fts` trigram indexes
  when the query's longest alphanumeric span (`_alphanumeric_span`) is ≥3 chars;
  otherwise via a SQL `LIKE` pattern (`?` → `_`, `*` → `%`, wrapped in `%`) over
  the normalized headword columns with `collapse_spaces=True`. Both paths then
  re-filter by the compiled regex ON THE RAW (accented) headword text
  (`pattern.search(r[1])`) — the regex is authoritative, FTS/LIKE only narrow.
- The regex is case-sensitive per letter (lowercase `ю` → `[юЮ]` matches both
  cases; uppercase `Ю` matches only `Ю`), so an uppercase query finds only
  uppercase headwords.
- Headword-search and empty-query results sort by the precomputed `collation_key`
  column (`r[9]`). It encodes
  `(alphabet_sort_key(sort_headword), entry_id_sort_key(entry_link) or
  entry_id_sort_key(hw_xml_id))` via `sort_keys.encode_order_key`, whose byte
  order equals the Python tuple order.
- Headword results keep their **display** headword (homonym number intact, e.g.
  `ґале́ра ІІ`); only the SORT key is stripped (`sort_headword` removes embedded
  `<n>` via `hw_text_excluding_n`). Distinct `<entry>`s such as `ґен І` and
  `ґен ІІ` stay separate rows; equal keys tie-break by entry ID.
- Empty query returns ALL entries (dictionary + sub_headwords) deduplicated by
  `(id, headword)`, with `!SOURCES` filtered out.
- Display headword text is always `resolve_headword(headword, keep_acc)`.

### Collation Rules (`alphabet_sort_key` in `dictionary_app/utils/sort_keys.py`)

- Letter-by-letter over the Belarusian alphabet (`ґ` after `г`, before `д`; `ё`
  between `е` and `ж`).
- Combining accents (U+0300/U+0301) are skipped, so accented and unaccented
  letters compare equally.
- Apostrophes (`'`, `’`, `ʼ`) are skipped entirely: `Юр'е` collates as `Юре`.
- Word breaks rank BELOW all letters (`-` = 0, space = 1; letters `а…я` = 2…34),
  so a multi-word entry groups right after its single headword; space ranks after
  hyphen.
- The pipe `|` (joining multiple `<hw>`s in a preview sort key) ranks like a
  space, so a completed first headword sorts before longer words with the same
  prefix; groups tie-break by second, third, … headword.
- Among equal prefixes, shorter words come first.
- Case is NOT in the letter rank: uppercase letters only decide ties AFTER
  character ranks, so `юр` sorts before `Юр` (and `юрка` before `Юрка`).
  `alphabet_sort_key` returns `(ranks, case_flags, accent_positions)`; Python
  compares ranks, then case flags, then accent positions (indices where a
  combining accent followed a vowel) — so an unaccented form sorts first.
- Other non-alphabet characters fall back to `len(alphabet) + ord(ch)`, sorting
  after letters with stable relative order.
- Both apps sort through this single key; XML files keep print order.

### Entry Formatting

- `format/format_entry.py`'s `process_element` is recursive: children go through
  `LinkHandler` for linkable tags (`src`, `st`, `see`), other tags are
  CSS-class-wrapped.
- Each child's CSS class is applied by the **parent iteration** (not
  self-formatting) — no double-wrapping.
- `<src>` links get `font-style: normal`; `<st>` links inherit italic.
- `LinkHandler.create_link` resolves source abbreviations via `SourceMapper`.
- `format_entry(xml_string, is_sources=False)` caches HTML in an LRU
  (`_format_cache`, `_FORMAT_CACHE_MAX_SIZE = 512`, keyed by the XML string).
  `FormatContext` is **cleared after every render** — write-only for the caller.
- **Comma-splitting quirks (preserve):**
  - If a `<hw>` tail starts with `,`, `:` or `;`, the symbol is split off and
    placed **inside** the `<span id="anchor">…,` so it stays clickable/linkable
    (bold). Two duplicate commas `,,` are both absorbed into the anchor.
  - If a `<g>` tail starts with `,`, the comma gets its own `<span class="g">`
    wrapper and the rest is plain text.
- **Paren rule (symmetric, same `process_element` logic):** any literal `(` / `)`
  inside an italicized tag (`g`, `ex`, `i`, `st`, `see`) is auto-wrapped in
  `<span class="p">`, so parens stay non-italic even without `<p>` markup. `<p>`
  in data still works and is redundant. `<src>` (already normal) is exempt.
- **Embedded-`<p>`-in-`<st>` rule:** a `<p>` child inside `<st>`/`<src>`/`<see>`
  is preserved as `<span class="p">…</span>` in the inner-content loop (NOT
  flattened), so `<st><p>презр.</p></st>` renders plain inside the italic `<st>`.
- **Square-bracket bold rule (preserve):** a literal `[`…`]` pair whose inner
  content contains **only** `<hw>` and/or `<src>`/`<st>` (at least one `<hw>`) is
  auto-wrapped in `<b>`. Detection (`_find_bracket_bold`) scans the element text
  and each child's tail and requires the brackets to be sibling text directly
  around the qualifying tags; other bracket uses are untouched.
- `_sense_matches_headword` / sense targeting: a `<sense>` counts only if its `n`
  attribute matches a target sense (digit for numeric, string otherwise).
  `<sense>` has NO `hw` attribute — sense→headword binding is only via the
  enclosing `<d>` bucket (`_d_variants`, i.e. `d_hw_variants`).
- Context (`FormatContext`) is module-level state set via
  `set_target_subheadword` / `set_target_senses` / `clear_target`;
  `process_element` reads it to prepend `👉` and wrap targeted senses/headwords in
  anchor spans. It is **cleared after every render** — never read it back to
  learn what was applied (see Navigation History).
- **Anchor IDs for a scoped target are entry-local:** a `<hw>` gets its `id`
  attribute when present, else `remove_accents(text)`. No entry-ID prefix, because
  the anchor is looked up only inside the already-resolved entry. Sense anchors
  use `SENSE_ANCHOR_PREFIX` (`sense_`).
- **Glyphs and schemes (single source):** `dictionary_app/utils/constants.py`
  defines every emoji/scheme — `ARROW_MARKER` (`👉`), `CROSS_MARKER` (`❌`),
  `BACK_ARROW` (`⬅️`), `FORWARD_ARROW` (`➡️`), `CHECK_MARK` (`✅`),
  `CHECK_BLANK` (`⬜`), `RADIO_ON` (`🟢`), `RADIO_OFF` (`⚪`), `GEAR_MARKER`
  (`⚙️`), `MAGNIFIER_MARKER` (`🔍`), `BOOKS_MARKER` (`📚`),
  `COLLAPSED_TRIANGLE_ENTITY`/`EXPANDED_TRIANGLE_ENTITY` (`▶`/`▼`),
  `SENSE_ANCHOR_PREFIX`, and `SCHEME_WORD/SOURCE/PREVIEW/WORD_ATTR/TOGGLE_SECTION`.
  Import the constant; never re-type a glyph/scheme. The arrow is used in the
  entry view (`headword-arrow`/`sense-arrow`) and injected by
  `render_sources.build_filtered_html` (which receives only the target anchor id);
  the nav bar uses `BACK_ARROW`/`FORWARD_ARROW`; the nav-bar close and
  sources-search close use `CROSS_MARKER`. Markup-only glyphs live in
  `markup_app/utils/constants.py`.
- **Tag attributes (single source):** `dictionary_app/utils/xml_schema.py` holds
  `ATTRIBUTES` (tag → ordered `(name, kind)`, `kind` = `TEXT`/`BOOL`), the
  `ATTR_*` constants, and helpers `attribute_names` / `is_boolean` /
  `unknown_attributes`. Every attribute read imports from here; the markup
  completion prompt reads the same registry. `sources.xml` (`section/@id`) is a
  separate document shape and intentionally NOT in this registry.
- **Arrow-suppression for homonyms:** whether the opened headword is the *main*
  one MUST compare against the full `<hw>` text via
  `SearchEngine.get_main_headword` (`''.join(hw.itertext()).strip()`), NEVER
  `hw.text` — `hw.text` drops an embedded `<n>` numeral ("ґен " + "І") and makes
  a homonym look like a sub-headword. Applies in ALL paths: entry-list click
  (`search_results_list.py`), see/word/nav links (`open_entry_by_headword`), and
  preview links. Sub-headword targets legitimately still get the arrow. A
  word/see link opening an entry whose target IS the main `<hw>` shows NO 👉. The
  comparison main does NOT skip `excl`.
- **Italics rule:** `.g`/`.ex`/`.i` are italic, but a nested `<hw>` inside a gloss
  (e.g. `один <hw>ґалёш</hw>`) and any inserted 👉 stay **non-italic** —
  `font-style: normal` on `.hw`, `.headword-arrow`, `.sense-arrow` in
  `dictionary_app/theme/styles.py`.

### Source Mapping (`SourceMapper`)

- Singleton (`__new__`, exported as `source_mapper`), loads
  `dictionary_app/data/source_mappings.json`, builds `_variant_to_abbr`. Every
  mapping currently lists exactly ONE (default) variant — keep new mappings
  single-variant.
- **Space-prefix rule (preserve):** six abbreviations (`акр.`, `п.`, `пав.`,
  `р.`, `с.`, `вол.`) are in `_space_prefixed_only` and match only when preceded
  by a space or at position 0. Do NOT remove or generalize this whitelist.
- `get_abbreviation(text)`: exact match first, then longest-variant-first.
- `extract_abbreviations(text)`: compiled combined regex returning `(abbr,
  variant)` pairs; same space-prefix check. Single-letter variants (currently only
  `С`) also require word boundaries, so `С` links standalone (`<src>С</src>`,
  `С.`) but not inside `Старадуб`/`Старина`.

### Window Layout (`MainWindow.setup_ui`)

- Vertical main layout: top row (search box [stretch 1] + insert-ґ button +
  sources button + settings button); bottom row (results list + splitter).
- Bottom row is a `QHBoxLayout` (not a splitter): results list at stretch 0
  (fixed `RESULTS_MIN_WIDTH`) + `bottom_splitter` at stretch 1.
- `bottom_splitter` (Horizontal) holds entry viewer (`SPLITTER_ENTRY_INITIAL`) +
  sources viewer (`SPLITTER_SOURCES_INITIAL`); both panes non-collapsible.
- Window default `WINDOW_DEFAULT_WIDTH` × `WINDOW_DEFAULT_HEIGHT`; minimum width
  is computed from visible panel minimums.
- `_update_min_width()` recalculates on every show/hide of the results list or
  sources panel.
- Global stylesheet: `GLOBAL_STYLE`; the results list uses `RESULTS_LIST_STYLE`
  (both in `dictionary_app/theme/styles.py`).

### Entry Viewer (`EntryViewer`)

- `DictTextBrowser` (QTextBrowser subclass) in a `QVBoxLayout` with
  `NavigationBar` above.
- Read-only, no external links (`setOpenExternalLinks(False)`), `ClickFocus`.
- `DictTextBrowser` installs `NoBlueFocusFrameStyle` and sets `ENTRY_STYLESHEET`
  as the document stylesheet.
- Document margin: `DOCUMENT_MARGIN` left/right via `rootFrame().frameFormat()` —
  **re-applied on every `setHtml`** (Qt resets the root frame format).
- `stored_html` holds the last displayed HTML for refresh/restore.
- `ScrollState` handles anchor scroll, resize re-scroll, and cached state restore
  (see Scroll State).
- `setSource` is overridden to block QTextBrowser navigation for `word:`,
  `source:`, and `preview:` (checked against `SCHEME_*`).
- `display_entry(result, formatter)` formats `result[2]` (the entry XML) and
  stores the HTML.

### Navigation Bar (`NavigationBar`)

- Fixed height `BAR_HEIGHT`; layout Back | Back-spacer | Flex-spacer | Forward |
  stretch | Close.
- Back/Forward: `NAV_BUTTON_WIDTH` wide, emoji labels
  (`BACK_ARROW`/`FORWARD_ARROW` + `strings.nav.back/forward`), flat transparent.
- Close: `IconButton`, `BUTTON_SIZE`.
- Visible only when `navigation_stack` has >1 entry; Back is hidden at index 0
  (replaced by a fixed-width invisible spacer to keep layout stable).
- Stack entries carry `{headword, sense_parts, entry_row_id, target}`; `push()`
  truncates forward history on a new push — see Navigation History.
- `_PREVIEW_SENTINEL` (`'__preview__'`, module constant in
  `dictionary_app/main_window.py`) is used as a headword — intercepted in
  `open_entry_by_headword` to restore the preview.

### Results List (`SearchResultsList`)

- `QListView` + `ResultsListModel` (a `QAbstractListModel`) renders only visible
  rows. The model stores `(display, headword)` pairs and exposes `DisplayRole`
  and `ROLE_HEADWORD`.
- Fixed width `RESULTS_MIN_WIDTH`, horizontal scrollbar always off, no focus
  policy — keyboard nav goes through `SearchBox` signals via
  `navigate_rows`/`select_row`.
- `ElidingDelegate` (shared with the markup app) elides in `initStyleOption` when
  text exceeds `viewport().width() - RESULTS_ITEM_PADDING` (`Qt.ElideRight`);
  `helpEvent` tests at HOVER time and calls `QToolTip.showText` directly (no
  `ToolTipRole`). Keep the strict `>` comparison.
- Tooltip = the row's `DisplayRole` (accent-RESOLVED headword).
- Font: Cambria/Times New Roman, 12pt bold (via `GLOBAL_STYLE`, which also covers
  `QListView`).
- Item CSS in `RESULTS_LIST_STYLE` (`QListView::item`): 3px left border
  transparent idle / grey hover / blue selected; white → hover → selected
  background; text always black.
- `display_results(results)` collapses same-entry duplicates, stores
  `current_results`, clears selection and the entry viewer, indexes rows into
  `_by_headword`/`_by_identity`/`_by_id`, sets model rows, selects row 0.
- `on_clicked(index, formatter, display_entry, scroll_to_anchor)` indexes
  **positionally** into `current_results[index.row()]` (bounds-guarded). It
  materializes the lazy row (`materialize_result`), computes `<hw>` equality via
  `get_main_headword` (does NOT skip `excl`), sets `set_target_subheadword` when
  the clicked headword differs from the main headword, then `display_entry` +
  scroll, and finally calls `navigation_bar.clear()` **before** returning the
  applied target (keep that order).
- `find_by_headword` / `find_by_identity` / `find_by_id` serve navigation.

### Search Box (`SearchBox`)

- `QLineEdit` subclass, fixed height `SEARCH_BOX_HEIGHT`.
- Signals: `navigate_up` (Up), `navigate_down` (Down), `activate`
  (Enter/Return).
- Style: white bg, 1px `COLOR_BORDER_DEFAULT`, `BORDER_RADIUS_SMALL`, thin
  padding.

### Settings Button (`SettingsButton`)

- Emoji gear (`GEAR_MARKER`), `BUTTON_SIZE`, subclass of `MenuButton` (shared
  size/cursor/`class="menu-button"`/style), opens `QMenu` on click.
- Menu: heading → separator → `_belarusian_radio` "Belarusian" (with
  sub-options) → `_russian_radio` "Russian".
- Built from `_ToggleOption` with `_RadioOption` and `_CheckOption`; radios use
  `RADIO_ON`/`RADIO_OFF`, sub-options use `CHECK_MARK`/`CHECK_BLANK`, indented
  with `MENU_INDENT_MARGINS`, inserted BEFORE the russian radio
  (`_add_scope_option` + `_all_scope_actions`).
- Sub-options (Belarusian): at least one stays checked — `_sync_sub_options`
  disables the only-checked one (`_CheckOption.set_active` applies
  `COLOR_DISABLED_FG`).
- `_headwords_option()` / `_examples_option()` return the sub-options;
  `_update_sub_visibility` hides them while the russian radio is active.
- `get_option_states()` returns the three-option dict (see Search Modes).

### Insert Letter G Button (`InsertLetterGButton`)

- Momentary `QPushButton` labelled `ґ` (exported as `INSERT_LETTER_G`),
  subclassing `MenuButton` so the letter renders at the shared 12pt size.
- `setFocusPolicy(Qt.NoFocus)` so a click never steals the cursor from a search
  bar — this enables insert-at-cursor.
- Sits between the search box and sources button. `_insert_letter_g` inserts at
  the cursor of whichever `SearchBox` has focus (`QApplication.focusWidget()` —
  main bar or sources search line); if none, it focuses the main search box first.

### Sources Panel (`SourcesPanel`)

- `DictTextBrowser` (read-only) + search `QLineEdit` + magnifier `IconButton`
  (`MAGNIFIER_MARKER`) + close `IconButton` (`CROSS_MARKER`) in a VBox;
  `get_widget()` returns the container.
- **Scrollbar-aware floating magnifier (preserve):** the magnifier overlays the
  viewer top-right in a 2-column `QGridLayout` (viewer spans both; column 1 is a
  spacer). `_update_floating_button_inset` sets column 1's minimum width to
  `overlay_right_inset(...)` on every `rangeChanged`, so the button clears the
  scrollbar when present and sits flush right otherwise.
- Toggle button (`SourcesButton`): `BOOKS_MARKER`, `MenuButton` subclass.
- Loaded from `dictionary_app/data/sources.xml`; HTML from
  `format/render_sources.build_filtered_html`.
- Search filters sections by text; no match renders `strings.nav.no_results`.
- `sources.xml` with no `<entry>` children → content `'<body></body>'` (no
  message string).
- Visibility tracked in `sources_visible`, toggled by the button.
- **Collapse/search state machine (preserve):** `_collapsed_sections` (set)
  tracks collapsed `<section>` ids. Search **auto-expands** matching collapsed
  sections; clearing the search restores the pre-search state. Hiding resets all
  collapsed state and the anchor.
- Section toggle links use `SCHEME_TOGGLE_SECTION`
  (`toggle-section:{id}`), rendered with
  `COLLAPSED_TRIANGLE_ENTITY`/`EXPANDED_TRIANGLE_ENTITY`; `ARROW_MARKER` is
  injected after the anchor span whose id was passed as `marker_anchor`.
- `scroll_to_source(abbr)`: strips trailing `:`/`.` for anchor lookup,
  auto-expands collapsed sections containing the target, calls
  `QApplication.processEvents()` before scrolling, then restores the focused
  widget and scroll position.
- `SourcesToggle` resizes the splitter (half entry / half sources) on show; on
  hide it combines entry+sources width back.

### Scroll State (`ScrollState`)

- `scroll_to_anchor(anchor)`: `viewer.scrollToAnchor(anchor)` + records
  `last_anchor`.
- `handle_resize()`: re-scrolls to `last_anchor` if set (no debounce timers).
- `cache_scroll()`: saves only the scrollbar value (an integer).
- `restore_content(html)`: sets HTML and restores the saved scroll value.
- `clear_cache()`: clears the scroll value and `last_anchor`.
- `last_anchor` is set to `None` after every `display_entry` and `clear_cache`.

### Scrollbar Geometry (`dictionary_app/utils/measure_scrollbars.py`)

- `scrollbar_extent(scroll_area)`: vertical scrollbar thickness via
  `verticalScrollBar().sizeHint().width()` (do NOT use
  `style().pixelMetric(PM_ScrollBarExtent)` — it crashes on stylesheet-proxied
  text edits).
- `vertical_scrollbar_shown(scroll_area)`: predicts via
  `verticalScrollBar().maximum() > 0`, never `isVisible()` (which lags the layout
  step emitting `rangeChanged`).
- `overlay_right_inset(container, scroll_area)`: right inset for a top-right
  overlay button = `container.width() - scroll_area.mapTo(container, ...).x() +
  scroll_area.frameWidth() + scrollbar_extent(scroll_area)`; `0` when hidden.
  Covers any frame/pane between container and scroll area (e.g. the markup tab
  pane), so the button's right edge meets the scrollbar's left edge.

### Link Routing (`on_link_clicked` + `open_entry_by_headword`)

- Schemes (`dictionary_app/utils/constants.py`): `word:`, `wordattr:`,
  `source:`, `preview:`. Routed through `LinkHandler.process_url` /
  `on_link_clicked` (see Entry Viewer for `setSource` blocking). `process_url`
  returns `(link_type, target, sense_parts, target_hw)`, with `target_hw` only for
  entry-scoped `word:E|H`/`wordattr:E|H`. `wordattr:` is the accent-preserving
  sibling of `word:` (same `E|H` shape), produced by `<see>` with `entry`/`hw`
  and parsed with `keep_accents=True` → `link_type == 'word-attr'`.
- **Word-URL forms:** `word:H` (whole entry; H = entry XML ID or headword text),
  `word:E|TEXT` / `word:E|H` (scoped: open entry E, then target TEXT/H *within
  that entry only*), `word:H n, m` (sense parts). **There is no `E#H` form** — do
  not reintroduce the `#`-fragment scheme.
- **`word:` links with `|` are built as raw `|`, but Qt percent-encodes it to
  `%7C` in the delivered `QUrl`.** `process_url` MUST `unquote()` before
  splitting on `|`, otherwise the target arrives as `E%7CH` and lookup fails.
- **`<see>` target forms:**
  - `<see>TEXT</see>` → `word:TEXT`
  - `<see hw="H">TEXT</see>` → `wordattr:H` (bare whole-entry; text is the label)
  - `<see entry="E">TEXT</see>` → `wordattr:E|TEXT`
  - `<see entry="E" hw="H">TEXT</see>` → `wordattr:E|H`
- **Accent preservation on attribute sees:** `entry`/`hw` targets are emitted via
  `LinkHandler.create_word_attr_link` under `wordattr:` and parsed with
  `keep_accents=True`. `on_link_clicked` routes them to
  `open_entry_by_headword(..., from_attr=True)`, which sets
  `headword_exact = from_attr and remove_accents(headword) != headword`; an
  accented target matches accent-PRESERVINGLY (`get_entry_by_headword(exact_headword=True)`
  → `_get_exact_headword`), while a text-only `word:` see stays
  accent-insensitive.
- **`<see>` text resolution (`get_entry_by_headword`) is EXACT — case- and
  space-preserving:** SQL equality on `normalized_headword`/
  `normalized_plain_headword` (spaces preserved) across BOTH tables, then exact
  `remove_accents(matched_text) == remove_accents(target)`; the first candidate
  matching with the SAME case wins (a case-distinct `Юр` vs `юр` is never
  conflated). `collapse_spaces=True` appears only in the search-box LIKE
  narrowing (`_like_pattern`); the final regex filter uses `\s+`. The click path
  never applies `normalize_jo_to_je`. `remove_accents` never touches `ў`
  (U+045E), so `<see>ў</see>` ↔ `<hw>ў</hw>` resolves in precomposed form.
- **Scoped target resolution is entry-local:** `get_entry_sub_headword(entry_row_id,
  target)` looks only inside the resolved entry's own sub-headwords, so a homonym
  elsewhere can never be picked up. It matches `<hw id>` exactly first, then
  de-accented sub-headword text **CASE-EXACTLY**; an **ambiguous text match
  (more than one)** returns `(None, None)` and the author must use the explicit
  `hw` attribute. A scope matching nothing or ambiguously is a MISS, not a
  fallback to the whole entry (see the empty-page rule below).
- **`<see>` with a homonym `<n>`**: the target is built from the whole `<see>`
  content (`itertext`, including an embedded `<n>`), so
  `<see>грыжа <n>ІІ</n>, 1, 2</see>` renders `грыжа ІІ, 1, 2` as a `word:` link to
  `грыжа ІІ` with senses `[1, 2]`. `LinkHandler.parse_link_text` is token-based:
  it detaches a *trailing* sense list (digit or single-letter tokens) from the
  word; a trailing Roman numeral (Cyrillic `І`/`і`, Latin `I`/`i`, `V`, `X`) stays
  on the word as the homonym marker. `get_entry_by_headword` falls back to
  comparing accent-stripped *display* headwords when the stripped index has no
  match — required because homonyms are indexed n-stripped.
- **Preview links** (`preview:{entry_id}|{anchor}`): URL-decode the anchor if it
  contains `%`; look up via `find_by_id` on current results first, else
  `get_entry_by_id`. Set `_highlight_entry = True`, save `_last_preview_html`,
  and push the headword with `_PREVIEW_SENTINEL` as the older entry.
- **`_PREVIEW_SENTINEL`**: `open_entry_by_headword` intercepts it and calls
  `_restore_preview()` (restores `_last_preview_html`, clears display state and
  nav bar). Preserve the sentinel and always set `_highlight_entry = True` when
  following a preview link. The nav-bar clear is INTENDED: previews terminate the
  entry-history chain.
- `open_entry_by_headword(headword, sense_parts=None, target_hw=None,
  from_navigation=False, from_word_link=False, from_attr=False,
  entry_row_id=None, target_subheadword=None)`:
  - `_PREVIEW_SENTINEL` → restore preview and return.
  - Resolves the entry: by `entry_row_id`, else by headword (current results by
    exact headword, then accent-resolved identity, then the DB, then
    `get_entry_by_xml_id` for `from_word_link`). Materializes the row and parses
    via `get_parsed_entry` (shared with `get_main_headword`).
  - **Resolves the entry FIRST, then the target inside it** when `target_hw` is
    set: `get_entry_sub_headword(resolved_entry_row_id, target_hw)` supplies the
    highlight word and local anchor. Never resolve against the whole corpus.
  - **Empty page when the scoped target is missing:** if the entry resolves but
    `get_entry_sub_headword` returns `(None, None)`, `result_to_display` is
    dropped and the click falls to the EMPTY step — a
    `<see entry="абора_p5_2">юра</see>` or `<see entry="E" hw="dangling">` must
    not present `абора` as if it contained the target. ONE exception: a scope
    naming the entry's **own main `<hw>`** (exact, then de-accented case-exactly)
    counts as a hit and renders the plain entry with no sub-target and no 👉,
    because the analyzer's `entry=` narrowing matches main + sub rows alike.
  - Sets format target: `from_navigation` + recorded `target_subheadword`
    re-applies it verbatim; else `set_target_senses(sense_parts, headword)` if
    sense parts; else `set_target_subheadword` if the resolved highlight word is
    non-empty and differs from the main headword; else `clear_target()`. There is
    no separate `from_word_link` branch: a link to the entry's own main `<hw>`
    falls through to `clear_target()` and renders WITHOUT 👉.
  - Tracks `current_display_xml` / `current_display_headword` /
    `current_display_row_id` / `current_display_senses` /
    `current_display_target`; reset on previews, search, close, unresolved.
  - Pushes to the nav stack only when NOT `from_navigation` and the **full
    identity** changed — entry row, headword, applied sub-headword target, or
    sense list (see Navigation History). If the previous headword was None but
    `_last_preview_html` exists, pushes `_PREVIEW_SENTINEL` as the older entry.
  - **Unresolved target:** when the headword/link resolves to nothing — or the
    entry resolves but its scoped target does not — the click is NOT a no-op: it
    becomes an explicit EMPTY step (pushes the target, same old-headword/sentinel
    rules) and displays an empty `<body></body>`. Keeps Back/Forward in increments.
  - Scrolls to the right anchor (`sense_{n}`, entry-local sub-headword anchor, or
    the headword).

### Navigation History (`NavigationBar.push` + display state)

- **Navigation identity = `(headword, entry_row_id, sub-headword target,
  sense_parts)`.** All four participate in dedup; sense/scoped links create a real
  step even when the entry is unchanged. A repeated identical click is a no-op.
- `push(headword, sense_parts, old_headword, entry_row_id=None, old_row_id=None,
  target=None, old_target=None, old_senses=None)`.
- The stack tip must be the entry actually being left. It can be stale because a
  results-list click calls `display_entry()` directly and never `push()` — and it
  has already cleared the stack (`navigation_bar.clear()` in `_present_clicked`),
  so the leaving state is seeded fresh; when the tip disagrees on headword, row,
  **or senses**, re-append the leaving state before the new one.
- `old_target`/`old_senses` must come from `current_display_*`, **not**
  `formatter.get_target_subheadword()` — `format_entry` clears the context after
  every render, so the formatter cannot report what was applied. Same for the
  combined-mode preview push in `on_result_clicked`: new `applied_target` as
  `target`, pre-click `old_target` as `old_target`, `_PREVIEW_SENTINEL` as the
  leaving headword.
- **Back/Forward restore the recorded target verbatim.** Target derivation runs
  only when `from_navigation` is False; the nav callback
  (`open_entry_by_headword_nav`, the only `from_navigation=True` caller) uses the
  stack entry's `target_subheadword`/`sense_parts` as-is.
- Unresolved targets are explicit empty steps (see Link Routing), so Back/Forward
  stay in increments.
- `same_senses(a, b)` (`dictionary_app/panels/entry_viewer.py`, re-exported from
  `dictionary_app.panels`) normalizes `None`/`[]`; use it for every sense
  comparison.

### Highlighting

- Entry opened from a preview → search terms highlighted with
  `COLOR_HIGHLIGHT_BG` (`dictionary_app/theme/styles.py`).
- Same-entry see links preserve the highlight (`_highlighted_entry_id` matches);
  different-entry see links clear it.
- Nav-bar close → `_dismiss_highlight()` re-renders without highlight and clears
  `_search_pattern`.
- Applied via `SearchEngine.apply_highlight`, delegating to
  `HighlightFormatter` (`format/highlight_formatter.py`). Exclusion is enforced at
  two levels:
  - `apply_highlight` protects `<a>` tags (`_ANCHOR_RANGE_RE`) and each excluded
    class block via `_protect_class_blocks` (manually tracks `<span>` nesting
    depth to find the matching close); protected blocks become placeholders, so
    the regex scans only highlightable (indexed-equivalent) text;
  - `_element_preview_content` wraps excluded children in
    `<span class="search-excluded">` and passes
    `exclude_classes=[EXCLUDED_HIGHLIGHT_CLASS]` (same class as the Exclusion
    Rules table);
  - text parts containing a placeholder are sub-split so a protected block never
    merges adjacent plain text into one skipped part;
  - `finditer` across concatenated parts, mapped back per part; placeholders are
    restored twice (nesting).
- In `MainWindow.display_entry` the exclude set starts with `hw` **always**. When
  `_search_normalize` is True (translations-only), `ex` is also excluded. When
  `_search_in_headwords` is True, `t` is excluded. `<hw>` is NEVER highlighted in
  any Belarusian-headword search variant.

### Global Shortcut

- Ctrl+C copies the selection from any QTextEdit via `install_global_copy`
  (`dictionary_app/utils/install_global_copy.py`), installed by both windows.

## Writing Conventions

- No comments in code unless essential.
- Module-level constants, no inline literals (`theme/layout_constants.py` for
  metrics, `utils/constants.py` for glyphs/schemes, `theme/styles.py` for
  colors/styles).
- All CSS in `dictionary_app/theme/styles.py` (one source of truth;
  `RESULTS_LIST_STYLE` included).
- Qt signals for cross-component communication; private methods use `_`.
- Pane = self-contained UI component (EntryViewer, SourcesPanel,
  SearchResultsList); Window = top-level OS window (MainWindow).
- **Docs must stay de-duplicated**: each fact in exactly ONE place; later mentions
  cross-reference (`see <section>`).
- **`dictionary_app/localization/strings.json` and
  `markup_app/localization/strings.json` are manually maintained by the user —
  NEVER rewrite them wholesale, re-serialize, or reformat.** Edit individual keys
  only, reading the file immediately before each edit and preserving all existing
  content (including indentation quirks).

## Database Schema

- `dictionary`: `(id INTEGER PRIMARY KEY, headword, sort_headword,
  normalized_headword, normalized_plain_headword, collation_key BLOB, entry_link,
  hw_xml_id, source_file, keep_acc)` — `headword` keeps the full display text;
  `sort_headword` drops embedded `<n>`; `collation_key` is the precomputed
  order-preserving key (see Collation Rules); `entry_link` is the entry's
  `<entry id>`; `hw_xml_id` its main `<hw id>`; `keep_acc` the main `<hw>`'s flag.
  Full XML lives in `entry_body`.
- `entry_body`: `(id INTEGER PRIMARY KEY, xml TEXT)` — full `<entry>` XML keyed
  by `dictionary.id`; joined by `materialize_result` and preview clicks, never
  carried by list queries.
- `sub_headwords`: `(id, headword, sort_headword, normalized_headword,
  normalized_plain_headword, collation_key BLOB, main_entry_id, link, hw_xml_id,
  keep_acc)` — `main_entry_id` points at the parent; `link` is the OWNING entry's
  XML ID (never an `E#H` compound); `hw_xml_id` is the sub-`<hw id>`; `keep_acc`
  is the sub-headword's own flag.
- `content_index`: `(id, entry_id, tag_type, searchable_text)`.
- `schema_meta`: `(key, value)` — holds `schema_version` (`_SCHEMA_VERSION`,
  currently 5).
- FTS5 trigram tables: `headword_fts(word)` (rowid = `dictionary.id`),
  `sub_headword_fts(word)` (rowid = `sub_headwords.id`) — populated from
  `normalized_headword`; `content_fts_t`/`content_fts_ex` (rowid =
  `content_index.id`) by `tag_type`.
- `source_file` tracks which file each entry came from (used by the markup save).
- **Indexed:** `content_index(tag_type, searchable_text)`,
  `content_index(entry_id)`, `dictionary(normalized_headword)`,
  `dictionary(normalized_plain_headword)`, `sub_headwords(normalized_headword)`,
  `sub_headwords(normalized_plain_headword)`. `dictionary.entry_link` is NOT
  indexed, so `entry_link` lookups scan (fine at current corpus). `get_entry_by_link`
  checks `dictionary.entry_link` first, then `sub_headwords.link` (returning the
  sub-headword's display headword with the parent's XML).

## Build / Rebuild

- Entry points: `dictionary_app/run.py` and `markup_app/run.py` each insert the
  project root on `sys.path`, construct `QApplication` first, then the window with
  `create_search_engine()` (`dictionary_app.db.create_search_engine`).
- `create_search_engine()`: `stale_source_files()` finds sources needing rebuild —
  the whole set if the DB is missing, else any `sources.xml` or `*.xml` in
  `dictionary_app/data/dictionary/` newer than the DB (non-XML artifacts
  ignored). If stale, `build_database(stale_files)` rebuilds ONLY those; else if
  `database_schema_is_current(db_path)` is false, `build_database()` does a full
  rebuild. Then returns `SearchEngine(db_path)`.
- `build_database(file_names=None)`: with no argument, or if the DB is missing or
  its schema outdated (`_schema_is_current`), does a FULL rebuild — drops/recreates
  `dictionary`, `entry_body`, `sub_headwords`, `content_index`, their indexes,
  `schema_meta`, and the four FTS5 tables; re-inserts every `*.xml` in sorted
  order plus `sources.xml`. Otherwise rebuilds incrementally: per named file,
  deletes that file's FTS rows by `rowid`, deletes its
  `dictionary`/`entry_body`/`sub_headwords`/`content_index` rows (by
  `source_file`), re-inserts from XML, then repopulates that file's FTS rows — FTS
  is maintained PER FILE, no full-corpus FTS scan. It reuses the existing DB file
  (never `os.remove`s it) so a second process holding the DB open does not block a
  rebuild on Windows.
- Inserts are batched (`_BATCH_SIZE`) with `PRAGMA synchronous = OFF` and a fixed
  cache size.
- `reindex_entry(entry_id, xml_text)` replaces ONE entry in place (delete by id →
  re-insert → repopulate its FTS rows), returning `(headword, entry_link,
  keep_acc)`; the markup app calls it after a save.
- `get_source_path(source_file)` maps a `source_file` (`'sources.xml'` or a split
  file name) to its absolute path; both apps use it. `get_source_names()` /
  `stale_source_files()` / `get_paths()` provide the file set and DB location.
- The SAME exclusion rules apply when building `content_index`. Translation index
  text is `normalize_jo(remove_accents(...))`; example index is
  `remove_accents(...)` only (no ё→е).
- `normalized_headword = remove_accents(sort_headword).lower()` (n-stripped, so
  homonym numerals are not searchable); `normalized_plain_headword =
  remove_accents(headword).lower()` keeps them.
- `sort_headword` = headword with embedded `<n>` removed
  (`hw_text_excluding_n`), used for ordering and as the discriminated text; the
  `headword` column keeps the full text.

## Performance / Scale Notes

- Already scale-safe: trigram FTS5 for headword (`headword_fts`/`sub_headword_fts`)
  and content (`content_fts_t`/`content_fts_ex`), precomputed `collation_key`,
  list rows carrying `NULL` instead of entry XML, indexes on the normalized
  headword columns, LRU `_parsed_cache` (≤ `_PARSED_CACHE_MAX_SIZE`) and
  `_preview_cache` (≤ `_PREVIEW_CACHE_MAX_SIZE`), LRU `_format_cache` in
  `format_entry`, virtualized `QListView` + `ResultsListModel`, and per-file
  FTS-scoped incremental rebuild.
- Projected at ~300k headwords: headword/content searches use trigram FTS when
  the longest alphanumeric span is ≥3 chars, degrading to `LIKE '%…%'` only for
  1–2-char spans; empty/all-results list rows are lightweight; per-click headword
  lookup is an indexed hit while `entry_link` still scans.
- Remaining 300k-scale work: build previews lazily (on click / visible rows) —
  `_preview_cache` only serves identical repeat queries; make short (1–2 char)
  spans fast — a B-tree cannot serve `LIKE '%…%'`; the first-run full build is
  synchronous (ship a prebuilt DB or build in the background if it matters).
  Per-edit rebuilds are always incremental.

## Key UI Wiring to Preserve

- **Settings button `_consume_next_press`**: after the menu closes
  (`aboutToHide`), if the cursor is still over the button,
  `_consume_next_press` makes `mousePressEvent` consume the release so the menu
  does NOT immediately re-open. Keep this workaround.
- **`show_all_entries()` first-show guard**: runs on the FIRST `showEvent` only
  (guarded by `_initial_shown`), so the initial load happens after the window is
  visible. Both apps use this.
- **Result-click state writes in `on_result_clicked`**: captures
  `old_target`/`old_senses` from the display state, stores
  `current_display_target = applied_target`, then unconditionally resets
  `current_display_senses = None`. A click that fails to materialize (`on_clicked`
  early-returns `None` — stale `QModelIndex` out of range, or an entry deleted
  while the list was live) clobbers `current_display_target` to `None` while the
  previous entry stays on screen; the next `push()` gets a wrong
  `old_target`/`old_senses`. Known edge; needs a stale index/DB row.
- **Combined-mode result click**: clicking a headword match while
  `_last_preview_html` exists pushes `_PREVIEW_SENTINEL` so Back returns to the
  previews.
- **`SearchResultsList.on_clicked` must call `navigation_bar.clear()` BEFORE
  returning the applied target** (see Results List).

# Markup App

Markup app code lives in `markup_app/` and imports `dictionary_app/` (never the
reverse). Before editing it, read `markup_app/AGENTS.md` — editor panes, save
flow, link markers, attribute completion, broken-link filters, entry loading.

Markup conventions and the raw-OCR → XML workflow are in
`markup_app/data/MARKUP_PATTERNS.md`. Everything shared with the dictionary app
is documented in this file: search modes, collation, `<hw excl="true">`,
previews, link routing, highlighting, DB schema, build, and UI wiring.
