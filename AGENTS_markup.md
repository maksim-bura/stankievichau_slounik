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
- Entry list: `QListWidget`, `NoFocus`, fixed width `RESULTS_MIN_WIDTH`=150px, horizontal scrollbar off
- Hover tracking via `eventFilter` on viewport (MouseMove + Leave events)
- Global stylesheet applied via `QApplication.instance().setStyleSheet(MARKUP_GLOBAL_STYLE)`

### Entry List
- Headword-only search (`search_in_headwords=True`)
- Fixed width (`RESULTS_MIN_WIDTH` = 150px), horizontal scrollbar off
- Ellipsis via custom `_BorderDelegate` (elides text that exceeds viewport width)
- Per-item painting via `_BorderDelegate`: custom background + left-border color per state
- Hover tracking via `eventFilter` on the viewport (MouseMove + Leave events)
- Items carry `UserRole+1` = headword, `UserRole+2` = entry_id

### Checked State
- Per-item key = `"{entry_id}:{headword}"` (sub-headwords are independent)
- Persisted to `build/markup_checked.json` via `CheckedState`
- `CheckedState.save()` called on every toggle (real-time persistence)
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
- `set_entry()` blocks signals during `setPlainText()` to avoid false dirty state

### Tag Buttons
- Two rows: `hw, g, t, tp, ex, src` | `lvl="1", lvl="2"`
- Auto-sized to fit content (no fixed width)
- `lvl="1"` / `lvl="2"` insert raw attribute text directly
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

### Save Flow
- Save button hidden when no changes; shown on `content_changed`
- `_save_current()`:
  1. Re-reads entry from source file via `_read_entry_from_source()` — matches the raw `<entry>...</entry>` block by **headword** (any `<hw>` in the block) instead of fragile full-string comparison; preserves the file's original markup (e.g. `<br></br>` stays as-is)
  2. Strips trailing newlines from old and new entry strings (`rstrip('\n')`)
  3. Finds old entry text in raw file content, replaces with new (ElementTree-serialized) text
  4. Writes back to file
  5. Updates **all** `current_results` entries sharing the same `entry_id` (main + sub-headwords all show the saved version), preserving each row's own headword/link/source_file
- `_read_entry_from_source(entry_id, source_file, headword)` takes an explicit `headword` param (accents-normalized via `remove_accents` + `normalize_jo`), falling back to the first entry only if no headword block matches
- Ctrl+S shortcut
- Auto-save on entry switch and `closeEvent`
- `source_file` column in `dictionary.db` tracks which file each entry came from

### Entry Loading
- `on_result_clicked` matches on **both** `entry_id` AND `headword` — sub-headwords share parent's `entry_id` so matching on `entry_id` alone would load the main headword's data instead
- After a save, the cache is updated in-place for all `entry_id`-matching rows so re-clicking loads the saved version
- `_read_entry_from_source()` locates entries by headword (accent-normalized) within raw `<entry>` blocks, preserving original file markup
- Checked toggle button updated on entry load

## Writing Conventions
- No comments in code unless essential
- Private methods use `_` prefix
- Markup-specific styles in `markup/styles.py`
- Shared styles (ENTRY_STYLESHEET, FLAT_BUTTON_STYLE) imported from `theme/widget_styles.py`
- Layout constants imported from `theme/layout_constants.py`
