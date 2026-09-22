# Markup App — Architecture Guide

## Goal
A dictionary entry editor for the Belarusian–Russian dictionary. Headword-only search, fixed QHBoxLayout (no splitter) with an entry list and a dual-mode editor (Text = raw XML, Author = rendered WYSIWYG). Saves changes back to the source XML files in `data/dictionary/`.

## Project Layout
```
markup/
├── __init__.py          # exports MarkupMainWindow
├── main.py              # entry point (python -m markup.main), uses db.bootstrap.create_search_engine()
├── main_window.py       # main window, search, entry list, save logic, checked-tracking delegate
├── editor.py            # dual-mode editor (Text/Author), tag buttons, Backspace logic
├── checked_state.py     # per-entry checked state, persisted to JSON
└── styles.py            # markup-specific stylesheets (palette colors imported from theme/widget_styles.py)
run_markup.py            # root-level launcher (same bootstrap)
```
Both launchers construct `QApplication` first, then `MarkupMainWindow(create_search_engine())`. `get_source_path` is imported from `db.build_database` (never re-derive paths).

## Key Design Decisions

### Window Layout (`MarkupMainWindow.setup_ui`)
- Fixed `QHBoxLayout` (no splitter): entry list at stretch 0 + editor at stretch 1
- Window default size: 765x650 px
- Top row: `SearchBox` (stretch 1) + checked-toggle button (`BUTTON_SIZE`=30x30) + Save button (`BUTTON_SIZE`, `TAG_BUTTON_STYLE`, initially hidden)
- Entry list: `QListWidget`, `NoFocus`, fixed width `RESULTS_MIN_WIDTH`=150px, horizontal scrollbar off
- Editor container min width set to `ENTRY_MIN_WIDTH`=300px
- Global stylesheet applied via `QApplication.instance().setStyleSheet(MARKUP_GLOBAL_STYLE)`

### Entry List
- Headword-only search (`search_in_headwords=True`)
- Fixed width (`RESULTS_MIN_WIDTH` = 150px), horizontal scrollbar off
- `ElidingDelegate` from `app/widgets/result_list_helpers.py` elides text exceeding viewport width; `select_row`/`navigate_rows` from the same module handle selection/keyboard navigation
- `_BorderDelegate` subclasses `ElidingDelegate` and owns all visual state: custom background + left-border color per state, driven by `_checked_state.is_checked(...)` + hover + selection
- Hover tracking via `eventFilter` on the viewport (MouseMove + Leave events); `_hovered_row` on the delegate drives the hover paint, `Leave` resets it
- Items carry `UserRole` = entry_link, `UserRole+1` = headword, `UserRole+2` = entry_id, `UserRole+3` = source_file
- First result row auto-selected after `_display_results`
- Keyboard nav: search box Up/Down signals route to `navigate_rows`; Enter triggers `_on_activate` → simulated click

### Checked State
- Per-item key = `"{source_file}:{entry_link}:{headword}"` — keyed on source file + entry link (not just entry_id) so collided/deduped headwords and sub-headwords stay independent
- Persisted to `build/markup_checked.json` via `CheckedState`
- `CheckedState.save()` called on every toggle (real-time persistence); writes UTF-8 with `ensure_ascii=False` (keeps Cyrillic) and `indent=2`, creating `build/` via `os.makedirs(exist_ok=True)` if missing.
- `CheckedState._load()` is resilient: an empty state file loads as `{}`; a corrupt (JSON-decode-failing) file is backed up to `{path}.bak` and the state resets to `{}` instead of crashing the app.
- API: `is_checked(source_file, entry_link, headword)`, `toggle(...)`, `set_checked(...)`, `get_all_checked()`
- `migrate(conn)` runs at startup and rewrites legacy-format keys (e.g. old `{entry_id}:{headword}`) to the current key schema
- Visual states via `_BorderDelegate.paint()`, with the shared palette (`COLOR_NORMAL_BG`/`COLOR_HOVER_BG`/`COLOR_SELECTED_BG`/`COLOR_BORDER_DEFAULT`/`COLOR_BORDER_SELECTED` from `theme/widget_styles.py`) plus local checked-state colors:
  - Non-checked idle: white bg, no border
  - Non-checked hover: `#fafafa` bg, grey border
  - Non-checked selected: `#edf7fd` bg, blue border
  - Checked idle: `#c8f7c5` bg, green border
  - Checked hover: `#b8f0b5` bg, green border
  - Checked selected: `#7cbf7a` bg, green border
- Text always painted black (palette override: `QPalette.Text` + `QPalette.HighlightedText` = black)
- Checked toggle button glyphs come from `utils/constants.py`: `CHECK_BLANK` (⬜) when unchecked, `CHECK_MARK` (✅) when checked; the Save button uses `FLOPPY_MARKER` (💾). Never re-type the emoji in this file.
- Entry list has no `item:hover`/`item:selected` CSS rules -- the delegate handles all visual states

### Editor
- `QTabWidget` with two panes: **Text** (editable `QTextEdit`) and **Author** (read-only `QTextEdit`)
- Author pane uses `ENTRY_STYLESHEET` from `theme/widget_styles.py` via `document().setDefaultStyleSheet()`
- Author pane re-renders on tab switch
- `EditorPane._is_modified` tracks changes; `content_changed` signal emitted on text change
- `set_entry()` blocks signals during `setPlainText()` to avoid false dirty state; also resets `_text_edit._pending_tag_delete = False` and clears extra selections so stale highlight/deletion state never carries over between entries
- **Plain-text paste enforced:** `setAcceptRichText(False)` + `canInsertFromMimeData` (text only) + `insertFromMimeData` → pasted HTML/rich content is inserted as plain text via `insertPlainText`, never as rich text (prevents hidden format junk inside the XML)
- Author pane render: `_render_author` tries `ElementTree.fromstring` + `format_entry`; on `ParseError` it falls back to showing the raw XML as plain text (so the author tab doesn't crash on a transiently invalid entry)

### Tag Buttons
- Two rows: `d, hw, g, t, tp, ex, src, br, see` | `lvl="1"` (a single level button)
- Auto-sized to fit content (no fixed width)
- `lvl="1"` inserts raw attribute text directly, no wrapping (handled in `insert_tag` before the wrap branch)
- Wrapping: wrap selected text in `<tag>…</tag>`, or insert empty `<tag></tag>` with cursor between
- Style: `TAG_BUTTON_STYLE` (transparent bg, no border, padding 2px 6px)
- The `tp` and `lvl="1"` buttons are kept in the editor for now (the `lvl="2"`/`lvl="3"` buttons were removed) even though the source XML files are currently stripped of `<tp>`/`lvl` markup — the buttons can re-insert it (see AGENTS.md → Source Data State).

### Backspace/Delete Logic (`_TagAwareTextEdit.keyPressEvent`)
1. **Inside a tag** (`_is_inside_tag`): normal character deletion (both keys)
2. **At a tag boundary** (`_pair_at_deletion_boundary`): the pair is highlighted (yellow, `COLOR_HIGHLIGHT_BG` from `theme/widget_styles.py`) and pending; the second press of the same operation removes both tags, keeping inner content. Highlight triggers ONLY when the character about to be deleted is a tag delimiter of the open/close pair:
   - **Backspace** next to the `>` of the opening tag (cursor right after `<t>`) or the `>` of the closing tag (cursor right after `</t>`)
   - **Delete** next to the `<` of the opening tag (cursor right before `<t>`) or the `<` of the closing tag (cursor right before `</t>`)
   - Cursor inside pair content (e.g. `<t>сорт{cursor}</t>` + Backspace) → **normal deletion** of the word char (deletes "т"), never the tags
3. **Selection matching `<tag>…</tag>` pattern** (`_PAIR_SELECT_RE`, Backspace only): removes both tags, keeps content, cursor after last word
4. **Any other Backspace/Delete**: normal deletion; clears pending state and extra selections (also any non-Backspace/Delete key)
- `_is_inside_tag()` checks if pos is between `<` and `>` of any tag
- `_pair_at_deletion_boundary()` maps the char about to be deleted (pos-1 for Backspace, pos for Delete) to a boundary of the enclosing pair and returns the pair only if that char is the `<`/`>` delimiter
- `_find_enclosing_tag_pair()` finds matching open/close tags using stack-based parsing (matches from `<` of the open tag onward so Delete-at-open works); the root `<entry>` pair is deliberately EXCLUDED — it returns `(None, None)`, never highlighting or deleting the entry wrapper
- State tracked via `_pending_tag_delete`, `_pending_open_tag`, `_pending_close_tag`
- **Deletion mechanics (preserve):** when deleting a pending pair, the CLOSE tag is removed FIRST, then the OPEN tag (removing close-then-open avoids shifting the other tag's char offsets). Signals are blocked during the batch edit, then `textChanged` is emitted manually so the save button appears.

**Known limitation (embedded/inner tags) — do NOT unintentionally regress or "fix":**
- When the cursor sits directly before an inner/embedded tag nested inside an outer tag (e.g. cursor before `<tp>` that is inside a `<t>`), `_find_enclosing_tag_pair` currently returns the OUTERMOST matching pair, so Backspace highlights/deletes the outer `<t>…</t>` (keeping all `<tp>` content) rather than just the inner `<tp>`. This is the CURRENT, shipped behavior. If you implement inner-tag deletion, do it as an additive preference for a tag at the exact cursor boundary and keep outer-pair deletion as the fallback — and preserve the close-first removal order.

### Save Flow
- Save button hidden when no changes; shown on `content_changed`
- `_save_current()`:
  1. Guard: returns immediately if no `current_result` or editor not modified (checked via `editor.editor.is_modified()`).
  2. Validation: parses the new XML with `ElementTree.fromstring`; on `ParseError` shows a warning `QMessageBox` and aborts (does NOT write).
  3. Re-reads the file, splits it into raw `<entry>...</entry>` blocks via regex, and locates the ORIGINAL block by comparing against the raw block text captured at load time (`self._loaded_raw[entry_id]`, from `on_result_clicked`). Saving requires the block to match **exactly once** — if it is missing or ambiguous (duplicate blocks present), it warns and aborts WITHOUT writing. This prevents accidental replacement of a wrong entry (no more `entries[0]` fallback).
  4. `content.replace(block, new_entry_string, 1)` replaces that unique block in place; everything else (blank lines between entries, other entries' original markup such as `<br></br>`) is preserved untouched.
  5. After a successful write: updates `_loaded_raw[entry_id]` to the new block, sets `_has_unsaved = False`, directly sets `editor.editor._is_modified = False` (bypass, since textChanged normally re-marks dirty), hides the save button.
  6. Updates **all** `current_results` entries sharing the same `entry_id` (main + sub-headwords all show the saved version), preserving each row's own headword/link/source_file
- `_read_entry_from_source(entry_id, source_file, headword=None, entry_link=None)`: matches a raw `<entry>` block by `link` attribute (`_block_link_matches`) and/or headword (`_block_matches`, accent- and ё-normalized). Returns `None` if nothing matches or on `ParseError`/`OSError` — it NEVER falls back to the first entry in the file.
- `_block_matches(block, target_norm)` compares every `<hw>` text in a block (accent- and ё-normalized) — handles entries with multiple `<hw>` (sub-headwords).
- Ctrl+S shortcut (`keyPressEvent`)
- Auto-save on entry switch (`on_result_clicked` calls `_save_current` first when `_has_unsaved`) and on `closeEvent`
- `source_file` column in `dictionary.db` tracks which file each entry came from

### Entry Loading
- `on_result_clicked` matches on **both** `entry_id` AND `headword` — sub-headwords share parent's `entry_id` so matching on `entry_id` alone would load the main headword's data instead
- When switching from a dirty entry it auto-saves first; then it re-reads the raw `<entry>` block from the source file and stores it in `self._loaded_raw[entry_id]` (also used as the editor text, so the editor always works from the file's exact markup). If no block is found, it keeps the DB-cached `full_entry`.
- Checked toggle button updated on entry load; save button hidden on entry load

### Entry List Order
- The list shows search-engine results in `search_engine` order (empty query = full dictionary UNION sub_headwords, sorted by `utils.text_utils.alphabet_sort_key` applied to the DB `sort_headword` column — headword text with embedded `<n>` homonym content stripped, so `ґале́ра ІІ` sorts by `ґале́ра`).
- Collation rules (see `alphabet_sort_key`): compares by Belarusian alphabet (ґ after г, before д); combining accents (U+0300/U+0301) are skipped so accented words collate by base letters; word breaks (space, hyphen) are strong dividers ranked BELOW all letters (hyphen before space), so a multi-word entry groups right after its single headword — `ґаз, ґаз сьвяціць, ґаза, ґазавая ґрана́та, …`; among equal prefixes, shorter words come first (shorter-first).

## Writing Conventions
- No comments in code unless essential
- Private methods use `_` prefix
- Markup-specific styles in `markup/styles.py`
- Shared styles and palette colors (`ENTRY_STYLESHEET`, `COLOR_*`) imported from `theme/widget_styles.py`
- Glyph constants (`CHECK_MARK`, `CHECK_BLANK`, `FLOPPY_MARKER`) imported from `utils/constants.py`
- Layout constants imported from `theme/layout_constants.py`