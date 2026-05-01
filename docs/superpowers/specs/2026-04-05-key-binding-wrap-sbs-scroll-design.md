# Design: Key Binding Fix / Wrap Toggle / Side-by-Side Independent Scroll

Date: 2026-04-05

## Overview

Three issues to address in `glreview`:

1. **Bug**: `c` (Add Comment) and `e` (Editor) keys in the right pane do nothing, and all subsequent operations become unresponsive.
2. **Feature**: Toggle line wrapping in diff display.
3. **Feature**: Side-by-side diff mode with independent horizontal scrolling per side.

---

## Issue 1: c/e Key Binding Fix

### Root Cause

Two compounding problems:

1. **Key interception**: In Textual 0.60+, `DataTable` may consume character key events before they bubble to `ContentPanel` or `App`. Pressing `c` activates DataTable's internal handling, preventing `ContentPanel.action_add_comment` from firing. Since DataTable holds focus and absorbs input, all subsequent key operations also fail.

2. **CommentDialog layout**: The current CSS applies `width: 80%; height: 60%` to the `CommentDialog` (ModalScreen) itself. Screens always fill the terminal, so `width/height` on a Screen has no effect. Internal widgets (TextArea etc.) expand to fill the full screen. The dialog is visually broken — potentially invisible as an overlay — while still consuming all input, giving the impression that "nothing happened" while all operations are blocked.

### Fix

**① Binding priority** — Add `priority=True` to both affected bindings so they fire before the focused widget's key handling:

- `ContentPanel.BINDINGS`: `Binding("c", "add_comment", "Add Comment", priority=True)`
- `App.BINDINGS`: `Binding("e", "open_in_editor", "Editor", priority=True)`

**② CommentDialog layout** — Wrap compose content in a `Vertical(id="dialog-container")` and move dialog styling from `CommentDialog` CSS to `#dialog-container`. The ModalScreen itself only needs `align: center middle` to center the inner container.

```
CommentDialog (ModalScreen)
  CSS: align center middle
└── Vertical #dialog-container
      CSS: width 80%, height 60%, background $surface, border thick $primary, padding 1 2
    ├── Label #comment-header
    ├── TextArea #comment-input
    ├── Label #comment-error
    └── Horizontal #comment-buttons
        ├── Button "Submit (Ctrl+S)"
        └── Button "Cancel (Esc)"
```

### Affected Files

- `glreview/tui/widgets/content_panel.py` — BINDINGS
- `glreview/tui/app.py` — BINDINGS
- `glreview/tui/screens/comment_dialog.py` — compose(), CSS in styles.tcss

---

## Issue 2: Diff Line Wrap Toggle

### Design

Add a boolean `_wrap_lines: bool = False` to `ContentPanel`. A new `w` key binding toggles it. When active and `_view_state == DIFF`, the diff is re-rendered immediately.

**Rendering change** in `_render_unified_table` and `_render_side_by_side_table`:

- `_wrap_lines=False` (default): `Text(content, overflow="ellipsis")` — long lines are truncated, horizontal scroll available
- `_wrap_lines=True`: `Text(content, overflow="fold")` — long lines wrap within the cell, DataTable auto-adjusts row height

**New binding**:

```python
Binding("w", "toggle_wrap", "Wrap", priority=True)
```

**New action** in `ContentPanel`:

```python
def action_toggle_wrap(self) -> None:
    if self._view_state != ContentViewState.DIFF:
        return
    self._wrap_lines = not self._wrap_lines
    if self._current_mr_iid and self._current_file_path:
        self.run_worker(
            self._load_diff(self._current_mr_iid, self._current_file_path),
            exclusive=True,
        )
```

### Affected Files

- `glreview/tui/widgets/content_panel.py` — `_wrap_lines` attribute, BINDINGS, `action_toggle_wrap`, rendering helpers

---

## Issue 3: Side-by-Side Independent Horizontal Scroll

### Architecture Change

Replace the single 4-column DataTable in side-by-side mode with two separate DataTables in a `Horizontal` container. Each table handles one side independently and can scroll horizontally on its own.

**Widget tree change**:

```
ContentPanel
├── Static #empty-hint
├── RichLog #content-log            (overview mode)
├── DataTable #diff-table           (unified mode)
└── Horizontal #sbs-container      (side-by-side mode)
    ├── DataTable #diff-table-left   columns: Old#, Old content
    └── DataTable #diff-table-right  columns: New#, New content
```

### Rendering

`_render_side_by_side_table` is split into:

- `_render_sbs_left_table(table, diff_text)` — populates `#diff-table-left` with (Old#, Old content) rows
- `_render_sbs_right_table(table, diff_text)` — populates `#diff-table-right` with (New#, New content) rows

Both receive the same parsed diff. Both share the same `_diff_row_lines` mapping (row index → new line number), populated from the left-table pass.

### Vertical Cursor Synchronization

When the cursor in one table moves, the other table mirrors it:

```python
def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
    if self._view_state != ContentViewState.DIFF:
        return
    row_idx = event.cursor_row
    # Update selected line
    if 0 <= row_idx < len(self._diff_row_lines):
        line_no = self._diff_row_lines[row_idx]
        if line_no is not None:
            self._selected_line = line_no
    # Sync cursor to sibling table in SBS mode
    if self._diff_mode == DiffViewMode.SIDE_BY_SIDE:
        source = event.data_table
        try:
            left = self.query_one("#diff-table-left", DataTable)
            right = self.query_one("#diff-table-right", DataTable)
            other = right if source is left else left
            other.move_cursor(row=row_idx, animate=False)
        except Exception:
            pass
```

### Focus and `c` Command

- On entering side-by-side mode, `#diff-table-left` receives initial focus.
- Pressing `Tab` cycles focus between left and right tables (Textual built-in).
- `action_add_comment` uses `self._selected_line` (updated on cursor move) — no change needed.

### CSS additions

```css
#sbs-container {
    height: 100%;
}

#diff-table-left,
#diff-table-right {
    width: 1fr;
    height: 100%;
}
```

### Affected Files

- `glreview/tui/widgets/content_panel.py` — compose(), on_mount(), `_show_diff_table()`, `_render_diff()`, `_render_sbs_left_table()`, `_render_sbs_right_table()`, `on_data_table_row_highlighted()`
- `glreview/tui/styles.tcss` — `#sbs-container`, `#diff-table-left`, `#diff-table-right`

---

## README Updates

- キーバインド表に `w` (折り返し切替) を追加

---

## Out of Scope

- MR のマージ・承認・クローズ操作
- 複数プロジェクト対応
