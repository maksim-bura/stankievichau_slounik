# Markup App — Architecture

The entry editor. It imports shared code from `dictionary_app/` and never the
other way around. This file covers markup-only behavior; the shared substrate
(search modes, collation, `<hw excl="true">`, previews, link routing,
highlighting, DB schema, build) is documented in `dictionary_app/AGENTS.md`,
and the raw-OCR → XML workflow in `markup_app/data/MARKUP_PATTERNS.md`.

## Goal

A dictionary entry editor. Headword-only search, fixed `QHBoxLayout` (no
splitter) with an entry list and a dual-mode editor (Text = raw XML, Author =
rendered WYSIWYG). Saves back to the source XML in
`dictionary_app/data/dictionary/`.

## Project Layout

```
stankievichau_slounik/
├── dictionary_app/            # shared code lives here
└── markup_app/                # DELETE this whole folder to remove the markup app
    ├── main_window.py         # window: search, list, toolbars/menus, save flow, filters
    ├── panels/                # MarkupEditor/EditorPane, XmlTextEdit, popup, delegates, models, tag buttons
    ├── services/              # broken links, link marks, completion context, duplicates, checked state, tag parsing
    │   └── build/             # runtime state (gitignored)
    ├── localization/          # load_strings.py + manually maintained strings.json
    ├── theme/                 # layout_constants.py, styles.py
    ├── utils/                 # constants.py (markup-only glyphs)
    ├── data/                  # dictionary_raw/*_raw.txt + MARKUP_PATTERNS.md
    └── run.py                 # launcher
```

**Deletable as a unit.** Nothing in `dictionary_app/` imports `markup_app/`.
Never add markup-only files/symbols to shared `dictionary_app/` modules; mirror
the shared structure instead (strings → `markup_app/localization/`, colors/
metrics/styles → `markup_app/theme/`, glyphs → `markup_app/utils/constants.py`,
non-UI logic → `markup_app/services/`, editor pane → `markup_app/panels/`,
runtime artifacts → `markup_app/services/build/`).

The launcher inserts the project root on `sys.path`, constructs `QApplication`
first, then `MarkupMainWindow(create_search_engine())`. `get_source_path` is
imported from `dictionary_app.db.build_database` (never re-derive paths).

## Key Design Decisions

### Window Layout (`MarkupMainWindow.setup_ui`)

- Fixed `QHBoxLayout` (no splitter): entry list at stretch 0 + editor at
  stretch 1. Default `WINDOW_DEFAULT_WIDTH` × `WINDOW_DEFAULT_HEIGHT`.
- Top row (`top_layout`, spacing `TOP_LAYOUT_SPACING`): `SearchBox` (stretch 1) +
  ґ-insert button + duplicates toggle + broken-links toggle + rebuild button (all
  `BUTTON_SIZE`). The checked toggle and Save button are NOT here — they live in
  the entry-window overlay (see Toolbar Buttons).
- Entry list: `QListView` + `ResultsListModel` (virtualized), `NoFocus`, fixed
  `RESULTS_MIN_WIDTH`, horizontal scrollbar off.
- Editor container min width `ENTRY_MIN_WIDTH`.
- Global stylesheet: `MARKUP_GLOBAL_STYLE`.

### Toolbar Buttons (`MarkupMainWindow.setup_ui`)

- **Duplicates toggle** (`_duplicates_toggle`): checkable, `DUPLICATES_MARKER`
  (👯), tooltip `app_buttons.duplicates.tooltip`. ON → `DuplicateResolver.filter`
  narrows the list to unresolved duplicate groups. `apply_pressed` mirrors the
  check state into the `pressed` property.
- **Duplicate resolution (`DuplicateResolver.filter` / `all_ids_resolved`):** rows
  are grouped by `resolve_headword(headword, keep_acc)`; a group of ≥2 is shown
  only when UNRESOLVED. Resolved (hidden) when every member row maps to a distinct
  entry/`hw_xml_id` identity — dictionary rows contribute `entry_link` +
  `hw_xml_id`, sub-headword rows `entry_link` plus the `hw_xml_id`s matching their
  `(main_entry_id, headword, link)`. `all_ids_resolved` requires every row to have
  at least one id and no id to repeat. Genuinely distinct homonym entries are
  hidden; colliding rows without distinct IDs stay listed.
- **Same-entry duplicate collapse (NORMAL list only):** with NO filter active
  (`_duplicates_toggle` off AND `_broken_mode is None`), `_display_results`
  collapses rows sharing a DB entry id + accent-resolved headword via
  `collapse_same_entry_duplicates` (first occurrence wins). With either filter
  active the collapse is skipped, so the 👯 groups/⛓️‍💥 flags are inspected per
  row. Clicking a collapsed row passes `occurrence=0` → first matching `<hw>`.
- **Broken-links toggle** (`_broken_links_toggle`): checkable,
  `BROKEN_LINKS_MARKER` (⛓️‍💥), tooltip `app_buttons.broken_links.tooltip`.
  Right-click opens `_broken_menu` — three independent checks from
  `app_buttons.broken_links.dropdown.*`: `missing_links`, `unresolved_links`,
  `ambiguous_g`, built as `BrokenCheckOption(text, checked=…)` rows mirroring the
  settings menu (CHECK_MARK/CHECK_BLANK + label, `SEARCH_BOX_HEIGHT` min-height,
  `MENU_OPTION_MARGINS`, `COLOR_DISABLED_FG` on the sole disabled one); at least
  one stays checked (`_sync_broken_option_active` disables the only-checked one).
  Clicking keeps the menu OPEN and re-filters live
  (`_on_broken_category_toggled`); all three checked = `MODE_UNION`, a subset =
  that category set. While the filter is OFF (`_broken_mode is None`)
  `_sync_broken_options` defaults every box to CHECKED; an ACTIVE subset mirrors
  exactly on reopen. Left-clicking the toggle sets the full union, clicking again
  clears (`_apply_broken_mode(None)`). The label has NO count suffix. Opening the
  menu sets the button's `pressed` property to `menu` (rendered as the clicked
  rim/background by `MENU_BUTTON_STYLE`).
- **Rebuild button**: `RELOAD_MARKER` (🔄), tooltip
  `app_buttons.rebuild_database.tooltip`, `_on_rebuild` (confirms leaving a dirty
  entry, closes the engine, `build_database()` full rebuild, clears
  caches/resolver, restores the previous search and entry).
- **Insert-ґ button** (`_insert_letter_g_button`): shared `InsertLetterGButton`
  between search box and duplicates toggle (see `dictionary_app/AGENTS.md` → Insert
  Letter G Button).
- **Checked toggle** (`_checked_toggle`) — in the ENTRY WINDOW (`EditorPane`
  top-right floating overlay via `QGridLayout`, NOT the top toolbar): plain
  button (no rim/background, `ENTRY_CHECKED_TOGGLE_STYLE`), checkable, showing
  CHECK_BLANK/CHECK_MARK. Left-click toggles the current entry
  (`_on_checked_toggle`); tooltip is state-correct (`entry_status.checked.tooltip`
  / `entry_status.unchecked.tooltip`). Right-click opens `_checked_menu` — one
  command option (`editor.entry_status.dropdown.uncheck_all`) wired to
  `_on_uncheck_all` (closes the menu, unchecks everything); its dropdown anchors
  at the button's label baseline so it opens adjacent to the glyph. Shown on entry
  load (`_load_result`); `MarkupEditor.checked_toggle` is the `EditorPane` alias.
  **Scrollbar-aware (preserve):** the overlay grid has tabs spanning two columns
  with column 1 as a spacer; `_update_overlay_inset` sets that column's minimum
  width to `overlay_right_inset(entry_wrapper, current_widget)` on both edits'
  `verticalScrollBar().rangeChanged` and on `_on_tab_changed`, so the overlay
  clears the active tab's scrollbar and sits flush right otherwise. The overlay is
  a `QHBoxLayout` holding the checked toggle and Save button (left→right).
- **Save button** (`_save_button`, `FLOPPY_MARKER` 💾) — same overlay, immediately
  RIGHT of the checked toggle (`EditorPane.save_button`; aliases on
  `MarkupEditor` / `MarkupMainWindow`), borderless via
  `ENTRY_CHECKED_TOGGLE_STYLE`, tooltip `editor.save.tooltip`. Hidden until the
  entry is modified; `_on_content_changed` shows it, `_save_current` /
  `_load_result` hide it; left-click → `_on_save` → `_save_current`. Ctrl+S also
  saves.
- **Shared context-menu pattern (preserve):** `QMenu` +
  `QWidgetAction.setDefaultWidget(...)`; opening (`_on_*_menu_requested`) sets the
  button's `pressed` property to `'menu'` (unpolish/polish) and pops at
  `mapToGlobal(QPoint(0, anchor))` (`_open_button_menu`; `anchor` defaults to
  `button.height()`, the checked toggle passes its label baseline); `aboutToHide`
  → `_on_*_menu_closed` sets `*_consume = _button_menu_consumed(btn)` (cursor
  still inside) and calls `_update_*_pressed`; the button's `eventFilter` branch
  swallows the NEXT `MouseButtonPress` while the consume flag is set, so the
  dismissing click does not toggle the button. `MenuCommandOption.mousePressEvent`
  accepts the event (menu stays open) and calls its callback (`None` = no-op).

### Entry List

- Headword-only search (`search_in_headwords=True` →
  `search_engine.search(text)`), sorted by the DB `collation_key` (see
  `dictionary_app/AGENTS.md` → Collation Rules).
- Fixed `RESULTS_MIN_WIDTH`, horizontal scrollbar off, `setUniformItemSizes(True)`,
  mouse tracking on.
- `ResultsListModel` rows are `(display, result)` pairs exposing `DisplayRole`,
  `ROLE_ENTRY_LINK`, `ROLE_HEADWORD`, `ROLE_ENTRY_ID`, `ROLE_SOURCE_FILE`.
- `BorderDelegate` (`panels/border_delegate.py`) subclasses `ElidingDelegate` and
  owns visual state: background + left-border color per state, driven by
  `CheckedState.is_checked(...)` + hover + selection. Hover tracking via
  `eventFilter` on the viewport (MouseMove + Leave); `set_hovered_row` drives the
  hover paint.
- First result row auto-selected after `_display_results` (via `select_row`).
- Keyboard nav: Up/Down from `SearchBox` → `navigate_rows` (shared helper);
  Enter → `_on_activate` → `on_result_clicked(currentIndex())`.

### Checked State

- Per-item key = `"{source_file}:{entry_link}:{headword}"` — keyed on source file
  + entry XML ID (not just entry_id) so collided/deduped headwords and
  sub-headwords stay independent.
- Persisted to `markup_app/services/build/markup_checked.json` via `CheckedState`.
- `CheckedState.save()` runs on every toggle; writes UTF-8 with
  `ensure_ascii=False` and `indent=2`, creating the folder via
  `os.makedirs(exist_ok=True)`.
- `_load()` is resilient: empty file → `{}`; corrupt JSON → backed up to
  `{path}.bak` and state resets to `{}`.
- API: `is_checked(source_file, entry_link, headword)`, `toggle(...)` (returns the
  new state and persists), `uncheck_all()`, `save()`, `migrate(conn)`.
- `migrate(conn)` runs at startup and rewrites legacy keys (e.g.
  `{entry_id}:{headword}`) to the current schema.
- Visual states via `BorderDelegate.paint()` using the shared palette
  (`COLOR_NORMAL_BG`/`COLOR_HOVER_BG`/`COLOR_SELECTED_BG`/
  `COLOR_BORDER_DEFAULT`/`COLOR_BORDER_SELECTED` from
  `dictionary_app/theme/styles.py`) plus local colors
  (`markup_app/theme/styles.py`):
  - Non-checked: white / `#fafafa` hover / `#edf7fd` selected; transparent /
    grey / blue border.
  - Checked: `#c8f7c5` / `#b8f0b5` hover / `#7cbf7a` selected; green border.
- Text always painted black (`QPalette.Text` + `QPalette.HighlightedText`).
- Checked toggle glyphs come from `dictionary_app/utils/constants.py`
  (`CHECK_BLANK`/`CHECK_MARK`); Save/Duplicates/Broken-links/Rebuild glyphs
  (`FLOPPY_MARKER`, `DUPLICATES_MARKER`, `BROKEN_LINKS_MARKER`, `RELOAD_MARKER`)
  come from `markup_app/utils/constants.py`. Never re-type an emoji.
- The entry list has no `item:hover`/`item:selected` CSS (`ENTRY_LIST_STYLE` only
  sets the transparent left border + padding) — the delegate handles states.

### Editor

- `MarkupEditor` = tag-button toolbar + `EditorPane`; `EditorPane` is the
  `QTabWidget` with **Text** (editable `XmlTextEdit`) and **Author** (read-only
  `QTextEdit`) panes. `MarkupEditor.pane` is the `EditorPane`.
- Author pane uses `ENTRY_STYLESHEET` via `document().setDefaultStyleSheet()` and
  re-renders on tab switch.
- `EditorPane._is_modified` tracks changes against `_baseline`; `content_changed`
  fires on text change; `link_marks_stale` is re-emitted from the Text edit.
- `set_entry()` blocks signals during `setPlainText()`, resets the char format,
  `_text_edit.reset_state()`, and clears extra selections, so stale
  highlight/deletion state never carries over.
- `get_xml()` returns `strip_link_markers(toPlainText())` — 🔗 markers are
  display-only and never reach the file.
- `mark_saved()` resets `_is_modified`/`_baseline`, clears the undo stack, and
  clears pair-delete snapshot state.
- **Plain-text paste enforced:** `setAcceptRichText(False)` +
  `canInsertFromMimeData` (text only) + `insertFromMimeData` → pasted HTML/rich
  content becomes plain text via `insertPlainText`.
- Author render (`_render_author`): `ElementTree.fromstring` + `format_entry`; on
  `ParseError` falls back to the raw XML as plain text.
- **Sub-headword mark / d-span underline:** clicking a sub-headword row calls
  `mark_sub_hw(headword, occurrence)` — moves the caret to the Nth matching
  `<hw>` (normalized), scrolls its line to the TOP of the viewport
  (`_scroll_line_to_top`, clamped like the dictionary's `scrollToAnchor`), and
  draws an orange bottom-underline (`COLOR_D_SPAN_UNDERLINE` = `#c2571a`,
  `_compute_d_span_sels`) across the innermost `<d>` containing it. A `<hw>`
  outside any `<d>` underlines the whole entry UNLESS the non-d region holds ≥2
  `<hw>`s (then nothing — ambiguous). Clicking a MAIN row calls
  `mark_main_non_d(headword, occurrence)`: with ≥1 `<d>`, underline the non-`<d>`
  region(s) (`non_d_regions`, one segment per gap); with NO `<d>` draw nothing and
  clear `_target_hw`. Both share `_target_hw`; `mark_sub_hw` clears
  `_non_d_underline` and vice versa, and `_compute_d_span_sels` is suppressed
  while `_non_d_underline` is non-empty. Same-entry duplicate rows differ by
  `occurrence`: `on_result_clicked` counts the clicked row's index among rows with
  the same `(entry_id, headword, entry_link)` triple and passes it to
  `_load_result`; the "already current" guard compares `current_occurrence` too.

### Link markers & dependency tooltip

- **Dependency marker:** each `<entry>` and `<hw>` opening tag TARGETED by a
  resolved `<see>` (or a local `<g hw=…>`) gets a 🔗 on its opening `<` in the
  Text pane — `LINK_MARKER = '\U0001F517'`, `_LINK_MARK_COLOR =
  QColor(70, 130, 180)`, emoji font Segoe UI Emoji.
- **Real marker characters, scan-based:** markers are REAL `LINK_MARKER`
  characters (never letter-spacing tricks) in a parallel "scan" coordinate space.
  `set_link_marks(offsets, tooltips, reset_undo)` maps clean-text offsets to scan
  positions via `LINK_PLACEHOLDER` (`'\uE000\uE001'`) deltas (`_clean_to_qt`).
  Every offset-based logic (tag parsing via `parse_xml_tags`, completion, save
  stripping) runs on the stripped clean text or counts/skips marker/placeholder
  chars. `_link_mark_texts` records each marker's host-text neighborhood; on
  `textChanged` the gate `_on_scan_changed` compares the snapshot and only
  re-runs `build_link_marks` when the host text changed.
- **Live enforcement + stale-signal rebuild:** key/paste edits that destroy a host
  `<` auto-clean orphaned markers inline (`_accept_completion_current`,
  `insertFromMimeData`, `keyPressEvent` all call `_on_scan_changed()` INSIDE the
  active edit block before the outermost `endEditBlock`). A `link_marks_stale`
  signal from the editor fires `_refresh_link_marks(reset_undo=True)`, rebuilding
  against the CURRENT text without recording undo.
- **Undo-merge invariant (critical):** ALL programmatic marker insertions/removals
  must run while an edit block is open (depth ≥ 1) so they merge into the user's
  undo command. Qt's `endEditBlock` emits a spurious `textChanged` at depth 0 —
  the `_last_scan_text` gate prevents a double-run, and the manual
  `_on_scan_changed()` calls run before the outermost `endEditBlock()`. Running
  enforcement at depth 0 creates phantom undo commands that starve Ctrl+Z.
- **Char-format reset invariant (critical):** `setPlainText` under `blockSignals`
  inherits the widget's stale `currentCharFormat` for ALL new characters.
  `EditorPane.set_entry` calls `setCurrentCharFormat(QTextCharFormat())` BEFORE
  `setPlainText()` (under blockSignals), and `set_link_marks` resets it again after
  inserting/removing markers. Note: `QTextCharFormat.fontFamily()`/
  `setFontFamily()` hard-crash (0xC0000005) in this PySide6 build — use
  `.font().family()` / `setFonts`.
- **Target set** (`link_marks_builder.build_link_marks(broken_links, text,
  entry_id)` → `(offsets, tooltips)`): marks `<entry>` when a resolved `<see>`
  row's `row[0]` (integer DB id) equals the current entry id; marks `<hw>` when
  its `id` (row[3]) or normalized headword (row[1]) matches, or a local
  `<g hw=…>` targets it. **Freshness gate:** for each resolved occ with
  `row[0] == entry_id`, `still_targets(occ)` verifies it would still resolve
  against the CURRENT text — `entry_attr` must match the current `<entry id=…>`
  or a current `<hw>` text; `hw_attr` (without `entry_attr`) must match a current
  hw id/text; a text-based see must have its sense-stripped normalized word in the
  current hw norms. Failing occs are skipped, so editing an entry's `id` and saving
  removes the emoji even though the DB still has the old row.
- **Tooltip (rich text, `LINK_TOOLTIP_DELAY_MS` hover):** `XmlTextEdit` sets
  `setMouseTracking(True)`; `_link_symbol_box(start)` is shared by `paintEvent`
  and `_link_mark_at(point)`; `mouseMoveEvent`/`leaveEvent` arm/clear a single-shot
  `_link_tooltip_timer` → `_show_pending_link_tooltip` → `QToolTip.showText`.
  - Line 1 (localized via `link_marks_builder.format_link_tooltip`):
    `strings.editor.link_dependencies.entry.tooltip` for `<entry>` markers,
    `...headword.tooltip` for `<hw>` markers.
  - Each dependency line = `&bull; ` + `<b>owning-hw(s)</b>` + `": "` + the raw
    `<see …>…</see>` span, all `html.escape()`d.
  - **Owning hws:** `BrokenLinkAnalyzer.owning_hw_texts(block, see_start)` buckets
    elements by nearest `<d>` (via `_collect_regions`) and returns the bucket's
    `<hw>` texts excluding `excl` (regex fallback if the block won't parse),
    displayed RAW (accents/ё preserved) joined with `', '`.
  - **Width:** `_widen_tooltip_html(text)` wraps lines in
    `<table width="{TOOLTIP_WIDTH_FACTOR×widest_line + TOOLTIP_WIDTH_PAD}">`
    (widest measured with `QFontMetricsF(self.font())`) — 50% wider than the
    longest line.
- Markers+tooltips are reset in `EditorPane.set_entry` (`reset_state`); a
  `<hw>`/`<entry>` targeted only by `<g hw=…>` still gets 🔗 but no tooltip.

### Attribute Completion (Content-Completion Assistant)

- Oxygen-style live prompt: typing a SPACE right after an opening tag's name pops
  a dropdown of that tag's attributes. The list filters on every keystroke;
  Up/Down move, Enter/Tab (or a click) inserts, Esc closes.
- **Spec source of truth:** `dictionary_app/utils/xml_schema.py` — one shared
  registry imported by BOTH the completion prompt (`services/completion_context.py`)
  and the app's attribute reads (formatters, `extract_content_text`, DB
  build/search, broken-links, markup source cache). `ATTRIBUTES` (tag → ordered
  `(name, kind)`), `ATTR_*` constants, helpers `attribute_names` / `is_boolean` /
  `unknown_attributes`. Currently `entry:id`, `hw:id,excl,keep-acc`, `g:hw`,
  `see:entry,hw,syn`, `sense:n`, `i:lang,excl`, `lang:code`. Add an attribute HERE
  (and to `markup_app/data/MARKUP_PATTERNS.md`) and it appears everywhere.
  `<sense>` has NO `hw` attr. `sources.xml` (`section/@id`) is intentionally not
  in the registry.
- **Context parser** (`detect_context(text, pos)`): scans back from the caret to
  the nearest `<` with no `>` in between (skipping `LINK_PLACEHOLDER`), reads the
  tag name, tokenizes the attribute region, and returns
  `CompletionContext(tag, present, fragment)` only when the caret is in the
  attribute-NAME slot. Returns `None` inside a quoted/unquoted value, in tag
  content, on a closed tag, on a partial tag name (no trailing space yet), and for
  tags with no spec. `present` attrs are excluded from candidates; matching is
  prefix, case-insensitive (`.candidates()`).
- **Insertion:** a TEXT attr inserts `name=""` with the caret between the quotes;
  a BOOL attr inserts `name="true"` at once (caret after). The typed `fragment` is
  replaced. Wrapped in `beginEditBlock`/`endEditBlock` so one undo removes it.
- **Popup** (`AttributePopup(QListWidget)`, `panels/attribute_popup.py`, parented
  to the edit): `Qt.Tool | FramelessWindowHint | WindowStaysOnTopHint |
  WindowDoesNotAcceptFocus` + `WA_ShowWithoutActivating` + `NoFocus`, so the
  editor keeps keyboard focus (keys handled in `XmlTextEdit.keyPressEvent` via
  `_handle_completion_key`) while mouse clicks still fire. Positioned under the
  caret (`cursorRect` → `mapToGlobal`), flipped above on screen overflow; width
  fits the longest item (`COMPLETION_MIN_WIDTH` + frame/row padding); height
  capped at `MAX_VISIBLE = 8` rows. Styled by `ATTRIBUTE_POPUP_STYLE`
  (`markup_app/theme/styles.py`) using the shared palette — item text is ALWAYS
  black (`color: black` on `::item`/`:hover`/`:selected`/`:selected:!active` PLUS
  a `QPalette.Text`+`HighlightedText`=black override), so the selected row stays
  black while focused like the entry list; `FONT_STACK`/12pt, bold inherited from
  the global `QListWidget` rule.
- **Trigger/retrigger:** only a typed SPACE (or a text-changing key while open)
  calls `_refresh_completion`; the popup does NOT reappear on caret re-entry
  (arrow keys hide it). It also hides on `mousePressEvent`, `focusOutEvent`, on
  `textChanged` (external edits), after accepting, on Esc, and whenever the parser
  returns no context/candidates.

### Tag Buttons

- Three groups (`TAG_BUTTON_GROUPS` in `markup_editor.py`):
  [`d, hw, n, g, sense, t, ex, st, src, see, lang`] + [`br`] + [`p, i, b`].
- One `QHBoxLayout`: `EDITOR_TOOLBAR_SPACING` between buttons,
  `EDITOR_TOOLBAR_GAP` between groups, trailing `addStretch()`.
- **Gap ceiling (preserve):** `EDITOR_TOOLBAR_GAP` (15px) is the MAXIMUM gap that
  fits the default window (editor content ≈615px). Raising it overflows/clips the
  row at the default width; wider windows give the extra space to the trailing
  stretch, never the gap.
- Auto-sized to fit content.
- Wrapping: wrap selected text in `<tag>…</tag>`, else insert empty
  `<tag></tag>` with the cursor between. `insert_tag` special-cases `br` →
  `<br />`, `sense` → `<sense n="">`, `lang` → `<lang code="">` (no selection:
  caret between the quotes; selection: wrapped).
- Style: `TAG_BUTTON_STYLE` (transparent, no border, padding 2px 6px, hover
  recolors the label); tabs live in a `UniformTabBar` (`tabSizeHint` = uniform
  width), tab position South, styled by `_MARKUP_TAB_STYLE` in
  `MARKUP_GLOBAL_STYLE`.

### Backspace/Delete Logic (`XmlTextEdit.keyPressEvent`)

1. **Inside a tag** (`is_inside_tag`): normal character deletion (both keys),
   EXCEPT when the deleted char is inside the tag NAME and the tag has a
   structural partner → mirrored rename (see Tag Name Renaming).
2. **At a tag boundary** (`pair_at_deletion_boundary`): the pair is highlighted
   (yellow, `COLOR_HIGHLIGHT_BG`) and pending; the second press of the same
   operation removes both tags, keeping inner content. Highlights ONLY when the
   char about to be deleted is a delimiter of the open/close pair:
   - **Backspace** next to the `>` of the opening tag (cursor right after `<t>`)
     or the closing tag (after `</t>`).
   - **Delete** next to the `<` of the opening tag (before `<t>`) or the closing
     tag (before `</t>`).
   - Cursor inside pair content (`<t>сорт{cursor}</t>` + Backspace) → **normal
     deletion** of the word char, never the tags.
3. **Selection matching `<tag>…</tag>`** (`_PAIR_SELECT_RE`, Backspace only):
   removes both tags, keeps content, cursor after the last word.
4. **Any other Backspace/Delete**: normal deletion; clears pending state and
   extra selections (any non-Backspace/Delete key does too).
- `parse_xml_tags.is_inside_tag()` checks if pos is between `<` and `>` of any tag.
- `pair_at_deletion_boundary(text, pos, forward)` maps the char about to be
  deleted (`pos-1` for Backspace, `pos` for Delete) to a tag delimiter; if it is
  not `<`/`>` it returns `(None, None)` (normal deletion).
- `_find_tag_pair_at_boundary` finds the owning pair via stack-based parsing: it
  pops open/close matches and returns the pair only if the char is that pair's
  open-start, open-`>`, close-`<`, or close-`>`. It is boundary-based (NOT
  position-in-range), so at a shared boundary like `<d><hw>…` a Backspace on the
  `>` resolves to `<d>` and a Delete on the `<` resolves to `<hw>`. Fully generic
  by tag NAME (including `entry`); NO hard-coded exclusion. Self-closing tags
  (`<br />`) are their own "pair" — highlighted/deleted at their `<`/`>`
  boundary; the deletion path handles `open_tag is close_tag` as a single
  removal, otherwise close-then-open order.
- State: `_pending_tag_delete`, `_pending_open_tag`, `_pending_close_tag`.
- **Direction guard:** the pending state records the arming key
  (`_pending_delete_forward`); the second press deletes only if the SAME key is
  pressed. The opposite key resets the state and runs its own boundary detection
  instead.
- **Any cursor movement** resets the pending state and clears the highlight via
  `cursorPositionChanged` (`_reset_pending_tag_delete`). The batch-delete flow
  runs under `blockSignals(True)`, so its internal moves don't trip this.
- **Deletion mechanics (preserve):** the CLOSE tag is removed FIRST, then the OPEN
  tag (avoids shifting the other tag's offsets). Both removals run inside
  `beginEditBlock()`/`endEditBlock()`, so one Ctrl+Z undoes BOTH. Signals are
  blocked during the batch edit, then `textChanged` is emitted manually so the
  save button appears.
- **Undo restores, highlights, AND re-arms:** at deletion time the pre-deletion
  text is snapshotted (`_pair_delete_snapshot`) with the removed tag spans and key
  direction (`_last_deleted_forward`). A `textChanged` handler compares the
  document against the snapshot; when it matches (the macro was undone), it
  re-arms the full pending state and highlight — so ONE next press of the same key
  deletes the pair again (Ctrl+Z + 1 press, not 2). Re-arm is deferred via
  `QTimer.singleShot(0, …)` (re-checking the text still matches) because Qt emits
  a trailing `cursorPositionChanged` after `textChanged` during undo. Direction
  guard still applies. Snapshot is cleared once matched, reset in `set_entry()`,
  overwritten by each new pair-deletion; typing between delete and undo does NOT
  trigger it.

### Tag Name Renaming (`XmlTextEdit` open↔close mirroring)

Editing characters inside a tag's NAME updates the structurally paired partner
tag on every keystroke.

- **Triggers:** a name character (ASCII letter/digit/`_`) inserted, deleted
  (Backspace/Delete), or replacing a selection lying entirely inside the tag NAME
  region (between `<`/`</` and the first non-name char). Edits to attributes, to
  `<`/`>` delimiters, or outside tags never mirror; the insertion point must be
  inside the name inclusive of its end (appending at the name end mirrors; typing
  a space right after the name does not).
- **Partner resolution:** structural stack pairing — `parse_xml_tags.scan_tags()`
  scans `<…>` spans (tolerating EMPTY names so the `<></>` transient works; `</>`
  is a closing tag, NOT self-closing) and `partner_tag()` matches open/close by
  name like `_find_tag_pair_at_boundary`, so nested same-name tags
  (`<t><t>…</t></t>`) resolve deterministically (inner↔inner, outer↔outer).
  Self-closing tags and tags with no structural partner are never mirrored.
- **Empty-name transient:** deleting a name down to `<></>` and retyping keeps
  mirroring (both sides tracked while empty), so a full rename stays in sync.
- **One undo step:** the typed change and the partner mirror run inside a single
  `beginEditBlock()`/`endEditBlock()` (`_apply_synced_name`), so one Ctrl+Z reverts
  BOTH.
- **Caret stays at the typed location:** the mirror edit never moves the caret to
  the partner; it shifts only if the partner edit sits before it (offset computed
  from the main edit's net length change, incl. the adjacent-pair case where the
  closing tag starts exactly at the opening tag's `end`).
- **Not hijacked:** Ctrl/Meta-modified Backspace/Delete (word delete) and
  non-name characters fall through to plain `QTextEdit`; pair-delete/selection
  flows are unaffected (sync hooks are the inside-tag delete branch and the
  plain-insert branch).

**Inner/outer resolution is deterministic:**
- At a boundary SHARED by two tags (e.g. between `<d>` and `<hw>`), direction
  decides: Backspace (deleting `>`) targets the outer tag; Delete (deleting `<`)
  targets the inner.
- At a boundary NOT shared (e.g. before `<g>` inside `<t>`, or right after
  `</g>`), the tag at the exact boundary wins, so the inner `<g>` is
  highlighted/deleted and the outer `<t>` is untouched.
- Preserve the close-first removal order for open/close pairs (self-closing
  single removal is the exception).

### Save Flow

- Save button hidden when unchanged; shown on `content_changed`.
- `_save_current()`:
  1. Guard: return `True` immediately if no `current_result` or
     `editor.pane.is_modified()` is false.
  2. Parse new XML with `ElementTree.fromstring`; on `ParseError` show
     `strings.dialog.invalid_xml` and abort (`False`, no write). The written text
     is `ElementTree.tostring(root, encoding='unicode')` — re-serialized, so the
     saved block is normalized XML (comments/attribute order not preserved).
  3. Require `source_file` and an existing source path; re-read the file via
     `_load_source_content` and locate the ORIGINAL block by exact comparison with
     the raw text captured at load time (`self._loaded_raw[entry_id]`, from
     `_load_result` / `_read_entry_from_source`). The block must match **exactly
     once**; if missing or ambiguous (duplicate blocks) warn and abort WITHOUT
     writing. Prevents replacing a wrong entry (no first-entry fallback).
  4. `content.replace(block, new_entry_string, 1)` replaces that unique block in
     place; everything else (blank lines, other entries' markup such as
     `<br></br>`) is preserved.
  5. Write UTF-8, then `reindex_entry(entry_id, new_entry_string)` so SQLite
     matches immediately (returns the new `(headword, entry_link, keep_acc)`; on
     failure keep the old values). Drop the file from `_source_cache`, update
     `_loaded_raw`, call `search_engine.invalidate_entry(entry_id)`, invalidate
     the broken-link cache, set `_has_unsaved = False`, call
     `editor.pane.mark_saved()` (clears modified flag + undo stack), hide the save
     button.
  6. Update **all** in-memory rows sharing the same `entry_id` via
     `_apply_saved_result` — both `current_results` and the model rows — with the
     saved entry's new `headword` / `entry_link` / `keep_acc`, keeping each row's
     own `source_file`; then refresh link markers. This matches on `entry_id`
     alone, so sub-headword rows of that entry also take the main headword.
     `_by_id_headword` is rebuilt and `_sub_headword_cache` cleared afterwards.
- `_read_entry_from_source(entry_id, source_file, headword=None, entry_link=None,
  keep_acc=0)`: matches a raw `<entry>` block by **entry XML ID** (`entry_link`,
  normalized accent- and ё-insensitively, via the `by_link` index) and/or by
  headword (`_block_matches`, accent- and ё-normalized, case-preserving). Returns
  `None` if nothing matches or on `ParseError`/`OSError` — NEVER falls back to the
  first entry.
- **Ambiguous headword/ID match → disambiguate by the row's own entry XML:** when
  ID-less lookup yields several candidates (distinct entries collided on a
  normalized headword, e.g. `ча́пацца`/`чапа́цца`, or two entries sharing a
  sub-headword), pick the candidate whose whitespace-stripped content equals that
  `entry_id`'s DB `entry_body` snapshot — never the first block for both rows. A
  single candidate keeps first-match behavior.
- **`entry_link` is the owning entry's own `<hw id>`/`<entry id>` and holds no
  `#H` suffix.** Sub-headword identity comes from `headword` + `hw_xml_id`.
- `_block_matches(block, target_norm)` compares every `<hw>` text in a block
  (accent- and ё-normalized, case-preserving) — handles multi-`<hw>` entries.
  Case is preserved because case-distinct headwords are separate entries. `excl`
  variants still match (an entry is loadable via either headword).
- `<hw excl="true">` is not a `dictionary`/`sub_headwords` row, so it never
  appears in this list either — the entry is listed under its first non-excl
  `<hw>` only.
- Ctrl+S shortcut (`keyPressEvent`).
- Auto-save on entry switch (`on_result_clicked` → `_confirm_leave` offers
  Save/Discard/Cancel when `_has_unsaved`) and on `closeEvent`.
- `source_file` in `dictionary.db` tracks each entry's file.

### Entry Loading

- `on_result_clicked(index)` reads `ROLE_ENTRY_ID`/`ROLE_HEADWORD`/
  `ROLE_ENTRY_LINK`, computes the row's `occurrence` among identical
  `(entry_id, headword, entry_link)` rows, resolves the full result from
  `_by_id_headword`, and skips when already current (same triple + occurrence).
- Matches on **both `entry_id` AND `headword`** — sub-headwords share the parent's
  `entry_id`, so entry_id alone would load the main headword.
- When switching from a dirty entry it confirms/saves first; `_load_result` then
  re-reads the raw `<entry>` block and stores it in `self._loaded_raw[entry_id]`
  (also the editor text, so the editor works from the file's exact markup). If no
  block is found it keeps the DB-cached XML.
- `_source_cache` (per file: `content`, `blocks`, `by_link`, `by_headword`) and
  `_sub_headword_cache` are invalidated on rebuild and after a save of that file.
  `_loaded_raw` grows one block per entry opened in a session and is popped only
  on source re-read failure.
- `_is_sub_headword(result)` compares the row headword with `dictionary.headword`
  for that id (cached in `_sub_headword_cache`); it decides `mark_sub_hw` vs
  `mark_main_non_d`.
- Checked toggle updated on load (`_apply_checked_visual`); save button hidden.

### Entry List Order

- The list shows `search_engine` order (empty query = full dictionary `UNION ALL`
  sub_headwords — duplicates by design, see `dictionary_app/AGENTS.md` → Search
  Modes) sorted by the precomputed DB `collation_key` (see
  `dictionary_app/AGENTS.md` → Collation Rules).
- Normal mode collapses same-entry duplicates after filtering (see Toolbar
  Buttons); filter modes show raw rows.

### Broken Links Analysis & Filtering (`_broken_filter`)

- `BrokenLinkAnalyzer` (`services/broken_link_analyzer.py`) takes a connection
  provider and a source-block provider. `flags()` is lazily computed and cached;
  `invalidate()` clears it (on rebuild and after a successful save).
- **Span-level detection** (`_span_flags`): partitions a block into regions =
  each `<d>` span (keyed by its nearest `<d>` ancestor) + the non-d region
  (`None`); a nested `<d>` gets its own region. Per region it collects
  `hw`/`g`/`see` descendants and computes:
  - `MODE_MISSING` / `MODE_UNRESOLVED` from each `<see>` via `_classify`.
  - `MODE_AMBIGUOUS_G` when the region has ≥2 `<hw>` AND ≥1 `<g>` AND (exactly
    one `<g>`, OR ≥2 `<g>` with at least one unresolved — single-g regions always
    fire). A `<g>` resolves if its `hw=` attr ID-matches or accent-matches an
    `<hw>` WITHIN the same entry.
  - Parsing via `ElementTree`; on `ParseError` falls back to `_span_flags_regex`
    (whole block as one region, all gs unresolved).
- **Headword index** = `dictionary` rows + `sub_headwords` rows (sub on par with
  main), cached and invalidated with the flags. Matching uses `normalize_headword`
  = `remove_accents(...)` (NEVER `ё`→`е`), quote-strip, `<n>`-tail append
  mirroring the formatting link-target logic.
- **Sense-tail stripping** (`split_sense_tail`, applied to every see-word at the
  top of classification): removes a trailing Arabic-digit sense list and returns
  the numbers, so `<see>абразок 1, 2</see>` is checked as `абразок` with
  `[1, 2]`. Roman numerals are NOT digits and stay on the word; a bare
  `<see>грыжа <n>ІІ</n></see>` is checked as the FULL headword `грыжа ІІ`, so it
  is `missing_links` when only plain `<hw>грыжа</hw>` exists.
- **Reverse sense check** (`_finalize_resolved` + `_row_has_senses`): when a
  stripped see-word carried a sense list and resolves to a SINGLE row, the entry
  must contain EVERY listed sense (`<sense n="…">` attributes, inner `<n>1.</n>`
  text as fallback) before counting as resolved; any missing sense →
  `missing_links`. Sees without a sense list skip this.
- **`<see>` classification** (`_classify(word, entry_attr, hw_attr)`; attributes
  and inner text both quote-stripped):
  - **Attributes decide when present:** if `entry=` and/or `hw=` is given,
    attribute handling runs FIRST and its outcome is returned directly — display
    text only narrows WITHIN the pinned entry. A dangling id, duplicate
    `<entry id>`, or an entry lacking the word is **missing_links**/
    **unresolved_links** even when the text alone is a valid unique headword.
    This mirrors runtime: `wordattr:` navigates BY the attribute.
    - `entry=` resolves by ID, falling back to a headword accent-match; no match →
      **missing_links**; several entries → **unresolved_links**; exactly one →
      narrow by `hw=` or by display text against that entry's `<hw>`s (0 →
      **missing_links**, 1 → **resolved**, 2+ → **unresolved_links**).
    - `hw=` alone resolves via `hw_xml_id` ID match or accent match: 1 →
      **resolved**, 0 → **missing_links**, 2+ → **unresolved_links**.
  - **No attributes** → EXACTLY ONE index row matching the see-word →
    **resolved** (or **missing_links** when a sense tail was present and the entry
    lacks any referenced sense); ZERO → **missing_links**; TWO+ →
    **unresolved_links**.
  - **Accent rule for `entry=`/`hw=` attributes:** an attr CONTAINING accents
    must equal the headword exactly (case+accents); an UNACCENTED attr matches
    accent-insensitively (`remove_accents` equality). Underscores stay literal.
- **Row mapping**: each flagged span maps to the rows of its `<hw>`s. A block's
  entry id is resolved by `<entry id>` else main-headword match; a block whose
  headword collides (≥2 candidate entries) keys its flags by
  `(source_file, None, hw_norm)` so all colliding rows match. `flags()` returns
  `{(source_file, entry_id_or_None, row_norm): {flags}}`.
- **Filtering**: `_broken_filter(results, mode)` matches a row by
  `(source_file, id, norm)` else `(source_file, None, norm)`; `mode` may be a
  string (`MODE_UNION` or one category) or an iterable of categories
  (`expand_broken_mode`) — matched as an intersection against the row's flag SET,
  so a subset filters the union of its categories. `_broken_mode` is `None` (off)
  or a set. Applied in `_display_results` AFTER the duplicates filter, so
  duplicates + broken mode is an INTERSECTION.
- **Row-click highlight** (`BrokenLinkAnalyzer.spans` →
  `EditorPane.highlight_broken_links`): loading an entry while `_broken_mode`
  includes `missing_links`/`unresolved_links` highlights every matching `<see>`
  with `COLOR_HIGHLIGHT_BG`. When the mode includes `ambiguous_g`,
  `ambiguous_spans(text)` returns the region's `<g>`/`<hw>` spans, highlighted
  with `COLOR_AMBIGUOUS_G_BG` (peach) / `COLOR_AMBIGUOUS_HW_BG` (lavender) via
  `highlight_grammar_marks` — one entry can show see-links and grammar marks at
  once. Recomputed by `_refresh_broken_highlight` on load and on mode change
  (`_see_span_mode` maps the active set to the see-link mode string); the span
  lists (`_broken_link_spans`/`_grammar_g_spans`/`_grammar_hw_spans`) SURVIVE
  cursor moves and clear only on another entry or leaving those modes.
  `_element_spans` pairs `<g>`/`<hw>` elements (document order) to opening-tag
  offsets; on `ParseError` a regex fallback flags the whole block.

## Writing Conventions

- No comments in code unless essential; private methods use `_` prefix.
- `markup_app/localization/strings.json` is manually maintained — never
  rewrite/reformat it; targeted key edits only (see `dictionary_app/AGENTS.md` →
  Writing Conventions).
- Markup-specific styles in `markup_app/theme/styles.py`.
- Shared styles/palette (`ENTRY_STYLESHEET`, `COLOR_HIGHLIGHT_BG`,
  `COLOR_NORMAL_BG`, `MENU_BUTTON_STYLE`, `GLOBAL_STYLE`, `flat_button_style`, …)
  imported from `dictionary_app/theme/styles.py`; markup-only palette
  (`COLOR_CHECKED_*`, `COLOR_D_SPAN_UNDERLINE`, `COLOR_AMBIGUOUS_*`,
  `COLOR_TRANSPARENT`, `COLOR_TEXT`) in `markup_app/theme/styles.py`.
- Glyphs `CHECK_MARK`/`CHECK_BLANK` from `dictionary_app/utils/constants.py`;
  markup-only glyphs (`FLOPPY_MARKER`, `RELOAD_MARKER`, `DUPLICATES_MARKER`,
  `BROKEN_LINKS_MARKER`, `LINK_MARKER`, `LINK_PLACEHOLDER`) from
  `markup_app/utils/constants.py`.
- Layout constants from `dictionary_app/theme/layout_constants.py`; markup-only
  metrics (`EDITOR_TOOLBAR_*`, `LIST_ITEM_BORDER_WIDTH`, `LINK_TOOLTIP_DELAY_MS`,
  `TOOLTIP_WIDTH_FACTOR`, `TOOLTIP_WIDTH_PAD`, `COMPLETION_*`) from
  `markup_app/theme/layout_constants.py`.
