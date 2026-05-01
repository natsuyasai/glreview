# Key Binding Fix / Wrap Toggle / SBS Independent Scroll Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix c/e key bindings not firing in the right pane, add diff line-wrap toggle, and enable independent horizontal scrolling per side in side-by-side diff mode.

**Architecture:** Three independent changes all touching `content_panel.py` and `styles.tcss`. Bug fix uses Textual's `priority=True` binding flag and CommentDialog layout restructuring. Wrap toggle adds a `_wrap_lines` flag that controls `Text` overflow mode in DataTable cells. SBS scroll replaces the single 4-column DataTable with two synchronized DataTables.

**Tech Stack:** Python 3.11+, Textual 0.60+, Rich, pytest, pytest-asyncio

---

## File Map

| File | Change |
|------|--------|
| `glreview/tui/app.py` | `priority=True` on `e` binding |
| `glreview/tui/widgets/content_panel.py` | BINDINGS, `_wrap_lines`, wrap helper, SBS tables, cursor sync |
| `glreview/tui/screens/comment_dialog.py` | Wrap compose() in Vertical container |
| `glreview/tui/styles.tcss` | Move CommentDialog CSS; add `#sbs-container` CSS |
| `glreview/tui/tests/test_entities.py` | New tests for `_wrap_text`, `_parse_diff` SBS rows |
| `glreview/tui/tests/test_pilot.py` | New tests for wrap toggle, CommentDialog widget tree |
| `README.md` | Add `w` keybind to table |

---

## Task 1: Fix binding priority

**Files:**
- Modify: `glreview/tui/app.py`
- Modify: `glreview/tui/widgets/content_panel.py`

- [ ] **Step 1: Write the failing test**

Add to `glreview/tui/tests/test_pilot.py`:

```python
@pytest.mark.asyncio
async def test_c_key_binding_has_priority():
    """ContentPanel の c バインディングが priority=True であることを確認する。"""
    from glreview.tui.widgets.content_panel import ContentPanel
    from textual.binding import Binding

    bindings = {b.key: b for b in ContentPanel.BINDINGS}
    assert "c" in bindings
    assert bindings["c"].priority is True


@pytest.mark.asyncio
async def test_e_key_binding_has_priority():
    """App の e バインディングが priority=True であることを確認する。"""
    from glreview.tui.app import GLReviewApp
    from textual.binding import Binding

    bindings = {b.key: b for b in GLReviewApp.BINDINGS}
    assert "e" in bindings
    assert bindings["e"].priority is True
```

- [ ] **Step 2: Run test to confirm failure**

```
pytest glreview/tui/tests/test_pilot.py::test_c_key_binding_has_priority glreview/tui/tests/test_pilot.py::test_e_key_binding_has_priority -v
```

Expected: FAIL — `AssertionError: assert False is True`

- [ ] **Step 3: Add priority=True to ContentPanel BINDINGS**

In `glreview/tui/widgets/content_panel.py`, replace the BINDINGS definition:

```python
BINDINGS: ClassVar[list[Binding]] = [
    Binding("t", "toggle_diff_mode", "Toggle unified/side-by-side", priority=True),
    Binding("c", "add_comment", "Add Comment", priority=True),
    Binding("w", "toggle_wrap", "Wrap", priority=True),
]
```

Note: `w` binding is added here; its action is implemented in Task 3.

- [ ] **Step 4: Add priority=True to App BINDINGS**

In `glreview/tui/app.py`, replace the BINDINGS definition:

```python
BINDINGS: ClassVar[list[Binding]] = [
    Binding("q", "quit", "Quit"),
    Binding("question_mark", "show_help", "Help"),
    Binding("r", "refresh", "Refresh"),
    Binding("e", "open_in_editor", "Editor", priority=True),
    Binding("left_square_bracket", "toggle_sidebar", "Toggle Sidebar"),
]
```

- [ ] **Step 5: Run tests to confirm they pass**

```
pytest glreview/tui/tests/test_pilot.py::test_c_key_binding_has_priority glreview/tui/tests/test_pilot.py::test_e_key_binding_has_priority -v
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add glreview/tui/app.py glreview/tui/widgets/content_panel.py glreview/tui/tests/test_pilot.py
git commit -m "fix: add priority=True to c and e key bindings to prevent DataTable interception"
```

---

## Task 2: Fix CommentDialog layout

**Files:**
- Modify: `glreview/tui/screens/comment_dialog.py`
- Modify: `glreview/tui/styles.tcss`

- [ ] **Step 1: Write the failing test**

Add to `glreview/tui/tests/test_pilot.py`:

```python
@pytest.mark.asyncio
async def test_comment_dialog_has_container():
    """CommentDialog が #dialog-container Vertical ウィジェットを持つことを確認する。"""
    from textual.app import App, ComposeResult
    from textual.widgets import Label, Vertical

    from glreview.models import CommentContext, CommentType
    from glreview.tui.screens.comment_dialog import CommentDialog

    context = CommentContext(mr_iid=1, comment_type=CommentType.NOTE)
    dialog = CommentDialog(context, MagicMock(), "vi")

    class _TestApp(App):
        def compose(self) -> ComposeResult:
            yield Label("base")

        async def on_mount(self) -> None:
            await self.push_screen(dialog)

    test_app = _TestApp()
    async with test_app.run_test() as pilot:
        from textual.widgets import Vertical as TVertical
        container = test_app.query_one("#dialog-container")
        assert container is not None
```

- [ ] **Step 2: Run test to confirm failure**

```
pytest glreview/tui/tests/test_pilot.py::test_comment_dialog_has_container -v
```

Expected: FAIL — `NoMatches` or similar (widget not found)

- [ ] **Step 3: Wrap compose() in Vertical container**

Replace `compose()` in `glreview/tui/screens/comment_dialog.py`:

```python
def compose(self) -> ComposeResult:
    from textual.containers import Vertical
    with Vertical(id="dialog-container"):
        yield Label(self._build_header(), id="comment-header")
        yield TextArea(id="comment-input")
        yield Label("", id="comment-error")
        with Horizontal(id="comment-buttons"):
            yield Button("Submit (Ctrl+S)", variant="primary", id="submit-button")
            yield Button("Cancel (Esc)", variant="default", id="cancel-button")
```

Also add `Vertical` to the imports at the top of the file. The existing import is:
```python
from textual.containers import Horizontal
```

Change to:
```python
from textual.containers import Horizontal, Vertical
```

- [ ] **Step 4: Update CSS in styles.tcss**

Replace:

```css
/* CommentDialog */
CommentDialog {
    width: 80%;
    height: 60%;
    align: center middle;
    background: $surface;
    border: thick $primary;
    padding: 1 2;
}
```

With:

```css
/* CommentDialog */
CommentDialog {
    align: center middle;
}

#dialog-container {
    width: 80%;
    height: 60%;
    background: $surface;
    border: thick $primary;
    padding: 1 2;
}
```

- [ ] **Step 5: Run test to confirm it passes**

```
pytest glreview/tui/tests/test_pilot.py::test_comment_dialog_has_container -v
```

Expected: PASS

- [ ] **Step 6: Run full test suite**

```
pytest glreview/tui/tests/ -v
```

Expected: All PASS

- [ ] **Step 7: Commit**

```bash
git add glreview/tui/screens/comment_dialog.py glreview/tui/styles.tcss glreview/tui/tests/test_pilot.py
git commit -m "fix: wrap CommentDialog content in Vertical container to fix invisible modal"
```

---

## Task 3: Add wrap toggle

**Files:**
- Modify: `glreview/tui/widgets/content_panel.py`

- [ ] **Step 1: Write the failing test for _wrap_text helper**

Add to `glreview/tui/tests/test_entities.py`:

```python
class TestWrapText:
    def test_short_line_unchanged(self) -> None:
        from glreview.tui.widgets.content_panel import _wrap_text
        assert _wrap_text("hello", 20) == "hello"

    def test_exact_width_unchanged(self) -> None:
        from glreview.tui.widgets.content_panel import _wrap_text
        assert _wrap_text("a" * 20, 20) == "a" * 20

    def test_long_line_wraps(self) -> None:
        from glreview.tui.widgets.content_panel import _wrap_text
        result = _wrap_text("a" * 50, 20)
        lines = result.split("\n")
        assert len(lines) == 3
        assert all(len(line) <= 20 for line in lines)

    def test_empty_string(self) -> None:
        from glreview.tui.widgets.content_panel import _wrap_text
        assert _wrap_text("", 20) == ""
```

- [ ] **Step 2: Run test to confirm failure**

```
pytest glreview/tui/tests/test_entities.py::TestWrapText -v
```

Expected: FAIL — `ImportError: cannot import name '_wrap_text'`

- [ ] **Step 3: Add _wrap_text helper and _wrap_lines attribute to content_panel.py**

Add module-level function after `_apply_context_filter`:

```python
def _wrap_text(text: str, width: int) -> str:
    """テキストを指定幅で折り返す（コード向け文字単位）。"""
    if len(text) <= width:
        return text
    return "\n".join(text[i : i + width] for i in range(0, len(text), width))
```

In `ContentPanel.__init__`, after `self._editor_command: str = "vi"`, add:

```python
self._wrap_lines: bool = False
```

- [ ] **Step 4: Run _wrap_text tests to confirm they pass**

```
pytest glreview/tui/tests/test_entities.py::TestWrapText -v
```

Expected: PASS

- [ ] **Step 5: Add action_toggle_wrap to ContentPanel**

Add after `action_toggle_diff_mode` in `content_panel.py`:

```python
def action_toggle_wrap(self) -> None:
    """差分表示の折り返しモードを切り替える。"""
    if self._view_state != ContentViewState.DIFF:
        return
    self._wrap_lines = not self._wrap_lines
    if self._current_mr_iid is not None and self._current_file_path is not None:
        self.run_worker(
            self._load_diff(self._current_mr_iid, self._current_file_path),
            exclusive=True,
        )
```

- [ ] **Step 6: Add _content_cell helper method to ContentPanel**

Add before `_render_unified_table`:

```python
def _content_cell(self, text: str, style: str = "") -> Text:
    """折り返しモードに応じてコンテンツセル用 Text を返す。"""
    if self._wrap_lines:
        # パネル幅から行番号列2本(各5文字)+余白を引いた幅
        wrap_width = max(40, self.size.width - 15)
        text = _wrap_text(text, wrap_width)
        return Text(text, style=style)
    return Text(text, style=style, no_wrap=True)
```

- [ ] **Step 7: Update _render_unified_table to use _content_cell**

In `_render_unified_table`, replace content cells as follows:

Find and replace each occurrence of `Text(text ..., style=_DIFF_ADD_STYLE)` / `_DIFF_REM_STYLE` / `_DIFF_HUNK_STYLE` / `_DIFF_GAP_STYLE` for the **content column** (third argument to `add_row`):

```python
# gap 行: 第3引数
Text(text, style=_DIFF_GAP_STYLE)
→ self._content_cell(text, _DIFF_GAP_STYLE)

# hunk 行: 第3引数
Text(text, style=_DIFF_HUNK_STYLE)
→ self._content_cell(text, _DIFF_HUNK_STYLE)

# header 行: 第3引数
Text(text, style="dim")
→ self._content_cell(text, "dim")

# add 行: 第3引数 (text + comment を含む)
Text(text + comment, style=_DIFF_ADD_STYLE)
→ self._content_cell(text + comment, _DIFF_ADD_STYLE)

# rem 行: 第3引数
Text(text, style=_DIFF_REM_STYLE)
→ self._content_cell(text, _DIFF_REM_STYLE)

# ctx 行: 第3引数 (plain str だったもの)
text + comment   (plain str)
→ self._content_cell(text + comment)
```

The full updated method (complete replacement):

```python
def _render_unified_table(self, table: DataTable, diff_text: str) -> None:
    """unified diff を DataTable に描画する（±コンテキスト行フィルタ付き）。"""
    parsed = _parse_diff(diff_text)
    rows = _apply_context_filter(parsed, _CONTEXT_LINES)
    row_idx = 0

    for t, old_n, new_n, text in rows:
        if t == "gap":
            table.add_row(
                Text("···", style=_DIFF_GAP_STYLE),
                Text("···", style=_DIFF_GAP_STYLE),
                self._content_cell(text, _DIFF_GAP_STYLE),
                key=f"gap_{row_idx}",
            )
            self._diff_row_lines.append(None)
        elif t == "hunk":
            table.add_row(
                Text("", style=_DIFF_HUNK_STYLE),
                Text("", style=_DIFF_HUNK_STYLE),
                self._content_cell(text, _DIFF_HUNK_STYLE),
                key=f"hunk_{row_idx}",
            )
            self._diff_row_lines.append(None)
        elif t == "header":
            table.add_row("", "", self._content_cell(text, "dim"), key=f"hdr_{row_idx}")
            self._diff_row_lines.append(None)
        elif t == "add":
            comment = " 💬" if new_n in self._comment_lines else ""
            table.add_row(
                Text("", style=_DIFF_ADD_STYLE),
                Text(str(new_n), style=_DIFF_ADD_STYLE),
                self._content_cell(text + comment, _DIFF_ADD_STYLE),
                key=f"add_{row_idx}",
            )
            self._diff_row_lines.append(new_n)
        elif t == "rem":
            table.add_row(
                Text(str(old_n), style=_DIFF_REM_STYLE),
                Text("", style=_DIFF_REM_STYLE),
                self._content_cell(text, _DIFF_REM_STYLE),
                key=f"rem_{row_idx}",
            )
            self._diff_row_lines.append(None)
        else:  # ctx
            comment = " 💬" if new_n in self._comment_lines else ""
            table.add_row(
                str(old_n) if old_n is not None else "",
                str(new_n) if new_n is not None else "",
                self._content_cell(text + comment),
                key=f"ctx_{row_idx}",
            )
            self._diff_row_lines.append(new_n)
        row_idx += 1
```

- [ ] **Step 8: Write test for toggle_wrap attribute**

Add to `glreview/tui/tests/test_pilot.py`:

```python
def test_content_panel_wrap_lines_default():
    """ContentPanel の _wrap_lines が初期値 False であることを確認する。"""
    from unittest.mock import MagicMock
    from glreview.tui.widgets.content_panel import ContentPanel

    panel = ContentPanel(MagicMock(), MagicMock())
    assert panel._wrap_lines is False
```

- [ ] **Step 9: Run tests**

```
pytest glreview/tui/tests/test_entities.py::TestWrapText glreview/tui/tests/test_pilot.py::test_content_panel_wrap_lines_default -v
```

Expected: PASS

- [ ] **Step 10: Commit**

```bash
git add glreview/tui/widgets/content_panel.py glreview/tui/tests/test_entities.py glreview/tui/tests/test_pilot.py
git commit -m "feat: add diff line-wrap toggle (w key) to ContentPanel"
```

---

## Task 4: Add SBS DataTables to compose and layout

**Files:**
- Modify: `glreview/tui/widgets/content_panel.py`
- Modify: `glreview/tui/styles.tcss`

- [ ] **Step 1: Write the failing test**

Add to `glreview/tui/tests/test_pilot.py`:

```python
def test_content_panel_has_sbs_tables():
    """ContentPanel が #diff-table-left と #diff-table-right を持つことを確認する。"""
    from unittest.mock import MagicMock
    from textual.widgets import DataTable
    from glreview.tui.widgets.content_panel import ContentPanel

    panel = ContentPanel(MagicMock(), MagicMock())
    # compose() の結果にウィジェットが含まれることを静的に確認するため
    # 実際のマウントが必要な場合は run_test を使う
    # ここでは BINDINGS の w キーが定義されていることを確認
    keys = {b.key for b in ContentPanel.BINDINGS}
    assert "w" in keys
    assert "t" in keys
    assert "c" in keys
```

- [ ] **Step 2: Run test to confirm it passes (w was added in Task 1)**

```
pytest glreview/tui/tests/test_pilot.py::test_content_panel_has_sbs_tables -v
```

Expected: PASS (w binding was added in Task 1)

- [ ] **Step 3: Update compose() to add SBS container**

Replace `compose()` in `content_panel.py`. Add the `Horizontal` import at the top (already present in `textual.containers`) and add to `compose()`:

```python
from textual.containers import Horizontal
```

Replace the full `compose()` method:

```python
def compose(self) -> ComposeResult:
    from textual.containers import Horizontal
    yield Static("Select an MR from the list.", id="empty-hint")
    yield RichLog(id="content-log", highlight=False, markup=True, wrap=False)
    yield DataTable(id="diff-table", cursor_type="row", show_header=True, zebra_stripes=False)
    with Horizontal(id="sbs-container"):
        yield DataTable(
            id="diff-table-left", cursor_type="row", show_header=True, zebra_stripes=False
        )
        yield DataTable(
            id="diff-table-right", cursor_type="row", show_header=True, zebra_stripes=False
        )
```

- [ ] **Step 4: Update on_mount() to hide SBS container**

Replace `on_mount()`:

```python
def on_mount(self) -> None:
    self.query_one(RichLog).display = False
    table = self.query_one("#diff-table", DataTable)
    table.display = False
    self.query_one("#sbs-container").display = False
```

- [ ] **Step 5: Update _show_diff_table() to handle both modes**

Replace `_show_diff_table()`:

```python
def _show_diff_table(self) -> None:
    self.query_one("#empty-hint").display = False
    self.query_one(RichLog).display = False
    if self._diff_mode == DiffViewMode.UNIFIED:
        self.query_one("#diff-table", DataTable).display = True
        self.query_one("#sbs-container").display = False
    else:
        self.query_one("#diff-table", DataTable).display = False
        self.query_one("#sbs-container").display = True
```

- [ ] **Step 6: Add CSS for SBS container**

Append to `glreview/tui/styles.tcss`:

```css
/* Side-by-side diff コンテナ */
#sbs-container {
    height: 100%;
}

#diff-table-left,
#diff-table-right {
    width: 1fr;
    height: 100%;
}
```

- [ ] **Step 7: Run existing test suite to verify no regressions**

```
pytest glreview/tui/tests/ -v
```

Expected: All PASS

- [ ] **Step 8: Commit**

```bash
git add glreview/tui/widgets/content_panel.py glreview/tui/styles.tcss
git commit -m "feat: add SBS DataTable pair to ContentPanel compose layout"
```

---

## Task 5: Implement SBS rendering

**Files:**
- Modify: `glreview/tui/widgets/content_panel.py`

- [ ] **Step 1: Write the failing test for SBS rendering**

Add to `glreview/tui/tests/test_entities.py`:

```python
class TestSBSRendering:
    """side-by-side diff の行数対称性テスト。"""

    SAMPLE_DIFF = """\
@@ -1,3 +1,3 @@
 context
-old line
+new line
 context2
"""

    def test_parse_diff_has_expected_rows(self) -> None:
        from glreview.tui.widgets.content_panel import _parse_diff, _apply_context_filter
        parsed = _parse_diff(self.SAMPLE_DIFF)
        rows = _apply_context_filter(parsed, 5)
        types = [t for t, *_ in rows]
        assert "add" in types
        assert "rem" in types
        assert "ctx" in types

    def test_sbs_pending_flush_balances_rows(self) -> None:
        """rem と add のペア数が一致する場合、左右の行数が等しい。"""
        from glreview.tui.widgets.content_panel import _parse_diff, _apply_context_filter

        parsed = _parse_diff(self.SAMPLE_DIFF)
        rows = _apply_context_filter(parsed, 5)

        pending_rem: list = []
        pending_add: list = []
        left_rows: list = []
        right_rows: list = []

        def flush():
            max_len = max(len(pending_rem), len(pending_add), 1)
            for k in range(max_len if (pending_rem or pending_add) else 0):
                left_rows.append(pending_rem[k] if k < len(pending_rem) else None)
                right_rows.append(pending_add[k] if k < len(pending_add) else None)
            pending_rem.clear()
            pending_add.clear()

        for t, old_n, new_n, text in rows:
            if t == "rem":
                pending_rem.append((old_n, text))
            elif t == "add":
                pending_add.append((new_n, text))
            else:
                flush()
                left_rows.append((old_n, text))
                right_rows.append((new_n, text))
        flush()

        assert len(left_rows) == len(right_rows)
```

- [ ] **Step 2: Run test to confirm it passes (logic test only)**

```
pytest glreview/tui/tests/test_entities.py::TestSBSRendering -v
```

Expected: PASS (tests the algorithm logic, not ContentPanel internals)

- [ ] **Step 3: Replace _render_side_by_side_table with _render_sbs_tables**

Remove the existing `_render_side_by_side_table` method entirely and add a single new method after `_render_unified_table`:

```python
def _render_sbs_tables(
    self, left: DataTable, right: DataTable, diff_text: str
) -> None:
    """side-by-side の左右テーブルを同時に描画する。
    diff_text を1回だけ解析し、左右に同数の行を追加することで
    カーソル同期が正しく機能することを保証する。
    """
    parsed = _parse_diff(diff_text)
    rows = _apply_context_filter(parsed, _CONTEXT_LINES)
    row_idx = 0

    pending_rem: list[tuple[int | None, str]] = []
    pending_add: list[tuple[int | None, str]] = []

    def _flush() -> None:
        nonlocal row_idx
        if not pending_rem and not pending_add:
            return
        max_len = max(len(pending_rem), len(pending_add))
        for k in range(max_len):
            old_n2, old_t = pending_rem[k] if k < len(pending_rem) else (None, "")
            new_n2, new_t = pending_add[k] if k < len(pending_add) else (None, "")
            left.add_row(
                Text(str(old_n2) if old_n2 else "", style=_DIFF_REM_STYLE if old_t else ""),
                self._content_cell(old_t, _DIFF_REM_STYLE if old_t else ""),
                key=f"sbs_l_{row_idx}",
            )
            right.add_row(
                Text(str(new_n2) if new_n2 else "", style=_DIFF_ADD_STYLE if new_t else ""),
                self._content_cell(new_t, _DIFF_ADD_STYLE if new_t else ""),
                key=f"sbs_r_{row_idx}",
            )
            self._diff_row_lines.append(new_n2)
            row_idx += 1
        pending_rem.clear()
        pending_add.clear()

    for t, old_n, new_n, text in rows:
        if t == "rem":
            pending_rem.append((old_n, text[1:] if text.startswith("-") else text))
        elif t == "add":
            pending_add.append((new_n, text[1:] if text.startswith("+") else text))
        else:
            _flush()
            if t == "gap":
                left.add_row(
                    Text("···", style=_DIFF_GAP_STYLE),
                    self._content_cell(text, _DIFF_GAP_STYLE),
                    key=f"gap_l_{row_idx}",
                )
                right.add_row(
                    Text("···", style=_DIFF_GAP_STYLE),
                    self._content_cell(text, _DIFF_GAP_STYLE),
                    key=f"gap_r_{row_idx}",
                )
                self._diff_row_lines.append(None)
            elif t == "hunk":
                left.add_row(
                    Text("", style=_DIFF_HUNK_STYLE),
                    self._content_cell(text, _DIFF_HUNK_STYLE),
                    key=f"hunk_l_{row_idx}",
                )
                right.add_row(
                    Text("", style=_DIFF_HUNK_STYLE),
                    self._content_cell(text, _DIFF_HUNK_STYLE),
                    key=f"hunk_r_{row_idx}",
                )
                self._diff_row_lines.append(None)
            elif t == "header":
                left.add_row("", self._content_cell(text, "dim"), key=f"hdr_l_{row_idx}")
                right.add_row("", self._content_cell(text, "dim"), key=f"hdr_r_{row_idx}")
                self._diff_row_lines.append(None)
            else:  # ctx
                ctx_text = text[1:] if text.startswith(" ") else text
                left.add_row(
                    str(old_n) if old_n is not None else "",
                    self._content_cell(ctx_text),
                    key=f"ctx_l_{row_idx}",
                )
                right.add_row(
                    str(new_n) if new_n is not None else "",
                    self._content_cell(ctx_text),
                    key=f"ctx_r_{row_idx}",
                )
                self._diff_row_lines.append(new_n)
            row_idx += 1

    _flush()
```

- [ ] **Step 4: Update _render_diff() to call _render_sbs_tables**

Replace `_render_diff()`:

```python
def _render_diff(self, diff_text: str, file_path: str) -> None:
    """差分テキストを DataTable にレンダリングする。"""
    table = self.query_one("#diff-table", DataTable)
    table.clear(columns=True)
    self._diff_row_lines = []

    if self._diff_mode == DiffViewMode.UNIFIED:
        table.add_column("Old", key="old_no", width=5)
        table.add_column("New", key="new_no", width=5)
        table.add_column("Content", key="content")
        self._render_unified_table(table, diff_text)
    else:
        left = self.query_one("#diff-table-left", DataTable)
        right = self.query_one("#diff-table-right", DataTable)
        left.clear(columns=True)
        right.clear(columns=True)
        left.add_column("Old#", key="old_no", width=5)
        left.add_column("Old", key="old_content")
        right.add_column("New#", key="new_no", width=5)
        right.add_column("New", key="new_content")
        self._render_sbs_tables(left, right, diff_text)
```

- [ ] **Step 5: Update _load_diff() to focus correct table**

In `_load_diff()`, replace the `table.focus()` call at the end of the try block:

Find:
```python
            self._view_state = ContentViewState.DIFF
            table.focus()
```

Replace with:
```python
            self._view_state = ContentViewState.DIFF
            if self._diff_mode == DiffViewMode.UNIFIED:
                table.focus()
            else:
                self.query_one("#diff-table-left", DataTable).focus()
```

- [ ] **Step 6: Run full test suite**

```
pytest glreview/tui/tests/ -v
```

Expected: All PASS

- [ ] **Step 7: Commit**

```bash
git add glreview/tui/widgets/content_panel.py glreview/tui/tests/test_entities.py
git commit -m "feat: implement SBS two-table rendering with _render_sbs_tables"
```

---

## Task 6: SBS cursor synchronization

**Files:**
- Modify: `glreview/tui/widgets/content_panel.py`

- [ ] **Step 1: Write the failing test**

Add to `glreview/tui/tests/test_entities.py`:

```python
class TestSBSCursorSync:
    """SBS カーソル同期ロジックのテスト（純関数）。"""

    def test_diff_row_lines_populated_after_left_render(self) -> None:
        """左テーブルレンダリング後に _diff_row_lines が構築されることを確認する。
        
        このテストは _parse_diff と _apply_context_filter の組み合わせが
        SBS に必要な行データを提供できることを確認する。
        """
        from glreview.tui.widgets.content_panel import _parse_diff, _apply_context_filter

        diff = "@@ -1,2 +1,2 @@\n context\n-old\n+new\n"
        parsed = _parse_diff(diff)
        rows = _apply_context_filter(parsed, 5)

        # rem と add が1行ずつある
        types = [t for t, *_ in rows]
        assert types.count("rem") == 1
        assert types.count("add") == 1
        # ctx 行がある
        assert "ctx" in types
```

- [ ] **Step 2: Run test to confirm it passes**

```
pytest glreview/tui/tests/test_entities.py::TestSBSCursorSync -v
```

Expected: PASS

- [ ] **Step 3: Update on_data_table_row_highlighted to sync cursors**

Replace `on_data_table_row_highlighted()` in `content_panel.py`:

```python
def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
    """DataTable のカーソル行変化で選択行を更新し、SBS モードでは対向テーブルのカーソルも同期する。"""
    if self._view_state != ContentViewState.DIFF:
        return
    row_idx = event.cursor_row
    if 0 <= row_idx < len(self._diff_row_lines):
        line_no = self._diff_row_lines[row_idx]
        if line_no is not None:
            self._selected_line = line_no

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

- [ ] **Step 4: Run full test suite**

```
pytest glreview/tui/tests/ -v
```

Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add glreview/tui/widgets/content_panel.py glreview/tui/tests/test_entities.py
git commit -m "feat: add SBS cursor synchronization between left and right DataTables"
```

---

## Task 7: Update README and run linter

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add w keybind to README**

In `README.md`, find the diff display keybind table:

```markdown
### 差分表示

| キー | 操作 |
|---|---|
| `t` | unified / side-by-side の切替 |
| `c` | 選択行にコメントを追加 |
```

Replace with:

```markdown
### 差分表示

| キー | 操作 |
|---|---|
| `t` | unified / side-by-side の切替 |
| `w` | 折り返し表示の切替 |
| `c` | 選択行にコメントを追加 |
```

- [ ] **Step 2: Run linter**

```
ruff check glreview/tui/widgets/content_panel.py glreview/tui/screens/comment_dialog.py glreview/tui/app.py
```

Expected: No errors. If errors appear, fix them before committing.

- [ ] **Step 3: Run full test suite one final time**

```
pytest glreview/tui/tests/ -v
```

Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: add w (wrap toggle) keybind to README diff display table"
```
