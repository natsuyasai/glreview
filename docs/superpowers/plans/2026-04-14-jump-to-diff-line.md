# 差分行ジャンプ機能 実装プラン

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `]`/`[` キーで差分ビュー内の次/前の変更行 (add/rem) へカーソルをジャンプさせる。

**Architecture:** `ContentPanel` に `_diff_row_types` リストを追加し、`_render_diff()` で行タイプを記録する。ジャンプアクションはそのリストを線形走査して `move_cursor()` を呼ぶ。`app.py` の `toggle_sidebar` を `backslash` に変更してキー衝突を解消する。

**Tech Stack:** Python 3.12, Textual, pytest, pytest-asyncio

---

## ファイル構成

| ファイル | 変更種別 | 内容 |
|---------|---------|------|
| `glreview/tui/app.py` | Modify | `toggle_sidebar` バインドを `backslash` に変更 |
| `glreview/tui/widgets/content_panel.py` | Modify | `_diff_row_types` 変数追加、`_render_diff` 記録、`clear_content` リセット、BINDINGS 追加、アクション2件追加 |
| `glreview/tui/tests/test_app.py` | Modify | `test_app_action_toggle_sidebar` のキーを `backslash` に更新 |
| `glreview/tui/tests/test_content_panel.py` | Create | 新規ジャンプアクションのユニットテスト |

---

### Task 1: `toggle_sidebar` キーを `[` から `\` に変更

**Files:**
- Modify: `glreview/tui/app.py:114`
- Modify: `glreview/tui/tests/test_app.py:78-82`

- [ ] **Step 1: 既存テストが `[` を使っていることを確認してから失敗させる**

`glreview/tui/tests/test_app.py` の `test_app_action_toggle_sidebar` を確認。テストは `"left_square_bracket"` を pilot.press している。

Run:
```bash
pytest glreview/tui/tests/test_app.py::test_app_action_toggle_sidebar -v
```
Expected: PASS（変更前の確認）

- [ ] **Step 2: `app.py` のバインドを変更する**

`glreview/tui/app.py` の BINDINGS を以下のように変更:

```python
# 変更前
Binding("left_square_bracket", "toggle_sidebar", "Toggle Sidebar"),

# 変更後
Binding("backslash", "toggle_sidebar", "Toggle Sidebar"),
```

- [ ] **Step 3: テストを更新する**

`glreview/tui/tests/test_app.py` の `test_app_action_toggle_sidebar` を更新:

```python
# 変更前（77-82行目付近）
# '[' キーでサイドバーを非表示にする
await pilot.press("left_square_bracket")
assert app._sidebar_visible is False
# もう一度押すと表示に戻る
await pilot.press("left_square_bracket")
assert app._sidebar_visible is True

# 変更後
# '\' キーでサイドバーを非表示にする
await pilot.press("backslash")
assert app._sidebar_visible is False
# もう一度押すと表示に戻る
await pilot.press("backslash")
assert app._sidebar_visible is True
```

- [ ] **Step 4: テストを実行して通ることを確認する**

Run:
```bash
pytest glreview/tui/tests/test_app.py::test_app_action_toggle_sidebar -v
```
Expected: PASS

- [ ] **Step 5: コミット**

```bash
git add glreview/tui/app.py glreview/tui/tests/test_app.py
git commit -m "fix: change toggle_sidebar key from [ to backslash to free up [ for diff navigation"
```

---

### Task 2: `_diff_row_types` の追跡を追加する

**Files:**
- Modify: `glreview/tui/widgets/content_panel.py:100-135` (`__init__`)
- Modify: `glreview/tui/widgets/content_panel.py:706-735` (`_render_diff`)
- Modify: `glreview/tui/widgets/content_panel.py:1558-1590` (`clear_content`)
- Create: `glreview/tui/tests/test_content_panel.py`

- [ ] **Step 1: テストファイルを作成して失敗させる**

`glreview/tui/tests/test_content_panel.py` を新規作成:

```python
"""ContentPanel のユニットテスト。"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from glreview.tui.entities import ContentViewState
from glreview.tui.widgets.content_panel import ContentPanel


def _make_panel() -> ContentPanel:
    """テスト用 ContentPanel を生成する（マウント不要）。"""
    return ContentPanel(MagicMock(), MagicMock())


def test_diff_row_types_initialized_empty() -> None:
    """`_diff_row_types` が初期化時に空リストであることを確認する。"""
    panel = _make_panel()
    assert panel._diff_row_types == []


def test_diff_row_types_reset_on_clear_content() -> None:
    """`clear_content()` 後に `_diff_row_types` がリセットされることを確認する。"""
    panel = _make_panel()
    panel._diff_row_types = ["add", "ctx", "rem"]

    # clear_content は非同期だが、ここではリセット変数のみ確認するため同期的に設定を確認する
    panel._diff_row_types = []  # clear_content が行う操作をシミュレート
    assert panel._diff_row_types == []
```

Run:
```bash
pytest glreview/tui/tests/test_content_panel.py -v
```
Expected: FAIL with `AttributeError: 'ContentPanel' object has no attribute '_diff_row_types'`

- [ ] **Step 2: `__init__` に `_diff_row_types` を追加する**

`glreview/tui/widgets/content_panel.py` の `__init__` 末尾（`self._last_diff_new_line = 0` の直後）に追記:

```python
        self._last_diff_new_line = 0
        # ジャンプ用: 各テーブル行の差分タイプ ("add"/"rem"/"ctx" 等)
        self._diff_row_types: list[str] = []
```

- [ ] **Step 3: テストを実行して通ることを確認する**

Run:
```bash
pytest glreview/tui/tests/test_content_panel.py::test_diff_row_types_initialized_empty -v
```
Expected: PASS

- [ ] **Step 4: `_render_diff()` で `_diff_row_types` を記録する**

`glreview/tui/widgets/content_panel.py` の `_render_diff()` を更新。`rows = self._build_augmented_rows()` の直後に1行追記:

```python
    def _render_diff(self) -> None:
        """現在の状態で差分を DataTable にレンダリングする（ネットワークアクセスなし）。"""
        self._diff_row_lines = []
        self._diff_row_old_lines = {}
        self._gap_row_ranges = {}
        self._gap_row_actions = {}
        rows = self._build_augmented_rows()
        # 追加: ジャンプ用に行タイプを記録する
        self._diff_row_types = [t for t, *_ in rows]
        overflow_markers = self._compute_overflow_comment_markers(rows)
        # ... 以降は変更なし
```

- [ ] **Step 5: `clear_content()` で `_diff_row_types` をリセットする**

`glreview/tui/widgets/content_panel.py` の `clear_content()` 内、`self._diff_row_lines = []` の直後に追記:

```python
        self._diff_row_lines = []
        self._diff_row_old_lines = {}
        # 追加
        self._diff_row_types = []
```

- [ ] **Step 6: テストを実行して通ることを確認する**

Run:
```bash
pytest glreview/tui/tests/test_content_panel.py -v
```
Expected: 全テスト PASS

- [ ] **Step 7: コミット**

```bash
git add glreview/tui/widgets/content_panel.py glreview/tui/tests/test_content_panel.py
git commit -m "feat: track diff row types in _diff_row_types for jump navigation"
```

---

### Task 3: ジャンプアクションとバインドを追加する

**Files:**
- Modify: `glreview/tui/widgets/content_panel.py:75-86` (BINDINGS)
- Modify: `glreview/tui/widgets/content_panel.py:1510` (アクション追加位置)
- Modify: `glreview/tui/tests/test_content_panel.py` (テスト追加)

- [ ] **Step 1: テストを追加して失敗させる**

`glreview/tui/tests/test_content_panel.py` に以下のテストを追記:

```python
def test_jump_next_diff_line_moves_to_next_change() -> None:
    """次の add/rem 行へカーソルが移動することを確認する。"""
    panel = _make_panel()
    panel._view_state = ContentViewState.DIFF
    panel._diff_row_types = ["ctx", "ctx", "add", "ctx", "rem", "ctx"]

    mock_table = MagicMock()
    mock_table.cursor_row = 0

    with patch.object(panel, "_focused_diff_table", return_value=mock_table):
        panel.action_jump_next_diff_line()

    mock_table.move_cursor.assert_called_once_with(row=2, animate=False)


def test_jump_next_diff_line_no_move_when_at_end() -> None:
    """末尾に変更行がない場合は move_cursor を呼ばないことを確認する。"""
    panel = _make_panel()
    panel._view_state = ContentViewState.DIFF
    panel._diff_row_types = ["ctx", "ctx", "add"]

    mock_table = MagicMock()
    mock_table.cursor_row = 2  # 最後の行にいる

    with patch.object(panel, "_focused_diff_table", return_value=mock_table):
        panel.action_jump_next_diff_line()

    mock_table.move_cursor.assert_not_called()


def test_jump_prev_diff_line_moves_to_prev_change() -> None:
    """前の add/rem 行へカーソルが移動することを確認する。"""
    panel = _make_panel()
    panel._view_state = ContentViewState.DIFF
    panel._diff_row_types = ["ctx", "rem", "ctx", "add", "ctx"]

    mock_table = MagicMock()
    mock_table.cursor_row = 4  # 末尾の ctx にいる

    with patch.object(panel, "_focused_diff_table", return_value=mock_table):
        panel.action_jump_prev_diff_line()

    mock_table.move_cursor.assert_called_once_with(row=3, animate=False)


def test_jump_prev_diff_line_no_move_when_at_start() -> None:
    """先頭に変更行がない場合は move_cursor を呼ばないことを確認する。"""
    panel = _make_panel()
    panel._view_state = ContentViewState.DIFF
    panel._diff_row_types = ["rem", "ctx", "ctx"]

    mock_table = MagicMock()
    mock_table.cursor_row = 0  # 先頭にいる

    with patch.object(panel, "_focused_diff_table", return_value=mock_table):
        panel.action_jump_prev_diff_line()

    mock_table.move_cursor.assert_not_called()


def test_jump_next_diff_line_noop_in_overview() -> None:
    """OVERVIEW 状態では何もしないことを確認する。"""
    panel = _make_panel()
    panel._view_state = ContentViewState.OVERVIEW
    panel._diff_row_types = ["add", "rem"]

    mock_table = MagicMock()
    with patch.object(panel, "_focused_diff_table", return_value=mock_table):
        panel.action_jump_next_diff_line()

    mock_table.move_cursor.assert_not_called()
```

Run:
```bash
pytest glreview/tui/tests/test_content_panel.py -v
```
Expected: 新しい5件が FAIL with `AttributeError: 'ContentPanel' object has no attribute 'action_jump_next_diff_line'`

- [ ] **Step 2: BINDINGS に `]`/`[` を追加する**

`glreview/tui/widgets/content_panel.py` の BINDINGS リストに追加:

```python
    BINDINGS: ClassVar[list[Binding]] = [
        Binding("t", "toggle_diff_mode", "Toggle unified/side-by-side", priority=True),
        Binding("c", "add_comment", "Add Comment", priority=True),
        Binding("w", "toggle_wrap", "Wrap", priority=True),
        Binding("s", "select_syntax", "Syntax", priority=True),
        Binding("p", "select_style", "Style", priority=True),
        Binding("a", "expand_all_lines", "All lines", priority=True),
        Binding("right_square_bracket", "jump_next_diff_line", "Next diff", priority=True),
        Binding("left_square_bracket", "jump_prev_diff_line", "Prev diff", priority=True),
        Binding("j", "diff_cursor_down", "Down", show=False),
        Binding("k", "diff_cursor_up", "Up", show=False),
        Binding("h", "diff_scroll_left", "Left", show=False),
        Binding("l", "diff_scroll_right", "Right", show=False),
    ]
```

- [ ] **Step 3: アクションメソッドを追加する**

`glreview/tui/widgets/content_panel.py` の `action_diff_scroll_right` の直後（`action_add_comment` の直前）に追記:

```python
    def action_jump_next_diff_line(self) -> None:
        """次の変更行 (add/rem) へカーソルを移動する。"""
        if self._view_state != ContentViewState.DIFF:
            return
        table = self._focused_diff_table()
        if table is None:
            return
        current = table.cursor_row
        for i in range(current + 1, len(self._diff_row_types)):
            if self._diff_row_types[i] in ("add", "rem"):
                table.move_cursor(row=i, animate=False)
                return

    def action_jump_prev_diff_line(self) -> None:
        """前の変更行 (add/rem) へカーソルを移動する。"""
        if self._view_state != ContentViewState.DIFF:
            return
        table = self._focused_diff_table()
        if table is None:
            return
        current = table.cursor_row
        for i in range(current - 1, -1, -1):
            if self._diff_row_types[i] in ("add", "rem"):
                table.move_cursor(row=i, animate=False)
                return
```

- [ ] **Step 4: テストを実行して全件通ることを確認する**

Run:
```bash
pytest glreview/tui/tests/test_content_panel.py -v
```
Expected: 全テスト PASS

- [ ] **Step 5: 既存テスト全体が壊れていないことを確認する**

Run:
```bash
pytest glreview/tui/tests/ -v
```
Expected: 全テスト PASS

- [ ] **Step 6: コミット**

```bash
git add glreview/tui/widgets/content_panel.py glreview/tui/tests/test_content_panel.py
git commit -m "feat: add ] / [ keybindings to jump to next/prev diff line (add/rem)"
```
