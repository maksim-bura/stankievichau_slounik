# Markup App — Architecture Guide

## Goal
A dictionary entry editor for the Belarusian–Russian dictionary. Headword-only search, fixed QHBoxLayout (no splitter) with an entry list and a dual-mode editor (Text = raw XML, Author = rendered WYSIWYG). Saves changes back to the source XML files in `data/dictionary/`.

## Project Layout
```
markup/
├── __init__.py          # exports MarkupMainWindow
├── main.py              # entry point (python -m markup.main)
├── main_window.py       # main window, search, entry list, save logic
├── editor.py            # dual-mode editor (Text/Author), tag buttons, Backspace logic
├── checked_state.py     # per-entry checked state, persisted to JSON
└── styles.py            # markup-specific stylesheets
run_markup.py            # root-level launcher
```

## Key Design Decisions

### Window Layout (`MarkupMainWindow.setup_ui`)
- Fixed `QHBoxLayout` (no splitter): entry list at stretch 0 + editor at stretch 1
- Window default size: 765x650 px
- Top row: `SearchBox` (stretch 1) + checked-toggle button (`BUTTON_SIZE`=30x30) + Save button (`BUTTON_SIZE`, `TAG_BUTTON_STYLE`, initially hidden)
- Entry list: `QListWidget`, `NoFocus`, fixed width `RESULTS_MIN_WIDTH`=150px, horizontal scrollbar off
- Editor container min width set to `ENTRY_MIN_WIDTH`=300px
- Hover tracking via `eventFilter` on viewport (MouseMove + Leave events)
- Global stylesheet applied via `QApplication.instance().setStyleSheet(MARKUP_GLOBAL_STYLE)`

### Entry List
- Headword-only search (`search_in_headwords=True`)
- Fixed width (`RESULTS_MIN_WIDTH` = 150px), horizontal scrollbar off
- Ellipsis via custom `_BorderDelegate` (elides text that exceeds viewport width)
- Per-item painting via `_BorderDelegate`: custom background + left-border color per state
- Hover tracking via `eventFilter` on the viewport (MouseMove + Leave events); `_hovered_row` on the delegate drives the hover paint, `Leave` resets it
- Items carry `UserRole+1` = headword, `UserRole+2` = entry_id (+ `UserRole` = entry_link)
- First result row auto-selected after `_display_results`
- `_navigate` clamps the selection to `[0, count)`, routed from the search box Up/Down signals; Enter triggers `_on_activate` → simulated click

### Checked State
- Per-item key = `"{entry_id}:{headword}"` (sub-headwords are independent — if the key were just entry_id, checking one sub-headword would check all of them)
- Persisted to `build/markup_checked.json` via `CheckedState`
- `CheckedState.save()` called on every toggle (real-time persistence); writes UTF-8 with `ensure_ascii=False` (keeps Cyrillic) and `indent=2`, creating `build/` via `os.makedirs(exist_ok=True)` if missing. Loaded lazily in the constructor.
- API: `is_checked(entry_id, headword)`, `toggle(entry_id, headword)`, `set_checked(entry_id, headword, value)`, `get_all_checked()`
- Visual states via `_BorderDelegate.paint()`:
  - Non-checked idle: white bg, no border
  - Non-checked hover: `#fafafa` bg, grey border
  - Non-checked selected: `#edf7fd` bg, blue border
  - Checked idle: `#c8f7c5` bg, green border
  - Checked hover: `#b8f0b5` bg, green border
  - Checked selected: `#7cbf7a` bg, green border
- Text always painted black (palette override: `QPalette.Text` + `QPalette.HighlightedText` = black)
- Checked toggle button: ⬜ (U+2B1C) when unchecked, ✅ (U+2705) when checked
- Entry list has no `item:hover`/`item:selected` CSS rules -- delegate handles all visual states

### Editor
- `QTabWidget` with two panes: **Text** (editable `QTextEdit`) and **Author** (read-only `QTextEdit`)
- Author pane uses `ENTRY_STYLESHEET` from `theme/widget_styles.py` via `document().setDefaultStyleSheet()`
- Author pane re-renders on tab switch
- `EditorPane._is_modified` tracks changes; `content_changed` signal emitted on text change
- `set_entry()` blocks signals during `setPlainText()` to avoid false dirty state; also resets `_text_edit._pending_tag_delete = False` and clears extra selections so stale highlight/deletion state never carries over between entries
- Author pane render: `_render_author` tries `ElementTree.fromstring` + `format_entry`; on `ParseError` it falls back to showing the raw XML as plain text (so the author tab doesn't crash on a transiently invalid entry)

### Tag Buttons
- Two rows: `hw, g, t, tp, ex, src` | `lvl="1", lvl="2", lvl="3"` (THREE level buttons — the third inserts `lvl="3"`)
- Auto-sized to fit content (no fixed width)
- `lvl="1"` / `lvl="2"` / `lvl="3"` insert raw attribute text directly, no wrapping (handled in `insert_tag` before the wrap branch)
- Wrapping: wrap selected text in `<tag>…</tag>`, or insert empty `<tag></tag>` with cursor between
- Style: `TAG_BUTTON_STYLE` (transparent bg, no border, padding 2px 6px)

### Backspace Logic (`_TagAwareTextEdit.keyPressEvent`)
1. **Inside a tag** (`_is_inside_tag`): normal character deletion
2. **Right after a tag** (`_is_adjacent_to_tag`): first Backspace highlights both tags via `setExtraSelections` (yellow `#FFF9C4` bg), sets `_pending_tag_delete = True`; second Backspace removes both opening and closing tag markup, keeping inner content
3. **Selection matching `<tag>…</tag>` pattern** (`_PAIR_SELECT_RE`): removes both tags, keeps content, cursor after last word
4. **Any other Backspace**: normal deletion; clears pending state and extra selections
- `_is_inside_tag()` checks if pos is between `<` and `>` of any tag
- `_is_adjacent_to_tag()` checks if pos is right at a tag boundary
- `_find_enclosing_tag_pair()` finds matching open/close tags using stack-based parsing
- State tracked via `_pending_tag_delete`, `_pending_open_tag`, `_pending_close_tag`
- **Deletion mechanics (preserve):** when deleting a pending pair, the CLOSE tag is removed FIRST, then the OPEN tag (removing close-then-open avoids shifting the other tag's char offsets). Signals are blocked during the batch edit, then `textChanged` is emitted manually so the save button appears.

**Known limitation (embedded/inner tags) — do NOT unintentionally regress or "fix":**
- When the cursor sits directly before an inner/embedded tag nested inside an outer tag (e.g. cursor before `<tp>` that is inside a `<t>`), `_find_enclosing_tag_pair` currently returns the OUTERMOST matching pair, so Backspace highlights/deletes the outer `<t>…</t>` (keeping all `<tp>` content) rather than just the inner `<tp>`. This is the CURRENT, shipped behavior. If you implement inner-tag deletion, do it as an additive preference for a tag at the exact cursor boundary and keep outer-pair deletion as the fallback — and preserve the close-first removal order.

### Save Flow
- Save button hidden when no changes; shown on `content_changed`
- `_save_current()`:
  1. Guard: returns immediately if no `current_result` or editor not modified (checked via `editor.editor.is_modified()`).
  2. Validation: parses the new XML with `ElementTree.fromstring`; on `ParseError` shows a warning `QMessageBox` and aborts (does NOT write).
  3. Re-reads entry from source file via `_read_entry_from_source()` — matches the raw `<entry>...</entry>` block by **headword** (any `<hw>` in the block) instead of fragile full-string comparison; preserves the file's original markup (e.g. `<br></br>` stays as-is)
  4. Serializes the new entry with `ElementTree.tostring(...)` then strips trailing newlines from BOTH old and new entry strings (`rstrip('\n')`) — this preserves blank lines between entries in the file
  5. Finds old entry text in raw file content; `content.replace(old, new, 1)` replaces only the FIRST occurrence; writes back to file
  6. After a successful write: sets `_has_unsaved = False`, directly sets `editor.editor._is_modified = False` (bypass, since textChanged normally re-marks dirty), hides the save button
  7. Updates **all** `current_results` entries sharing the same `entry_id` (main + sub-headwords all show the saved version), preserving each row's own headword/link/source_file
- `_read_entry_from_source(entry_id, source_file, headword)`:
  - Takes an explicit `headword` param (accents-normalized via `remove_accents` + `normalize_jo`), used to match raw `<entry>` blocks via `_block_matches`; falls back to the FIRST entry only if no headword block matches (and if parsing succeeds). Returns `None` on `ParseError`/`OSError`.
  - `_block_matches(block, target_norm)` compares every `<hw>` text in a block (accent- and ё-normalized) — handles entries with multiple `<hw>` (sub-headwords).
- Ctrl+S shortcut (`keyPressEvent`)
- Auto-save on entry switch (`on_result_clicked` calls `_save_current` first when `_has_unsaved`) and on `closeEvent`
- `source_file` column in `dictionary.db` tracks which file each entry came from

### Entry Loading
- `on_result_clicked` matches on **both** `entry_id` AND `headword` — sub-headwords share parent's `entry_id` so matching on `entry_id` alone would load the main headword's data instead
- When switching from a dirty entry it auto-saves first; then if `_has_unsaved` or the cached `xml_text` is empty, it re-reads fresh from the source file (via `_read_entry_from_source`, see Save Flow) and updates the matching `current_results` row (by entry_id) with the fresh text, so re-clicking loads the saved version
- Checked toggle button updated on entry load; save button hidden on entry load

## Writing Conventions
- No comments in code unless essential
- Private methods use `_` prefix
- Markup-specific styles in `markup/styles.py`
- Shared styles (ENTRY_STYLESHEET, FLAT_BUTTON_STYLE) imported from `theme/widget_styles.py`
- Layout constants imported from `theme/layout_constants.py`
