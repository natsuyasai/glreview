# 差分行ジャンプ機能 設計書

**日付**: 2026-04-14  
**対象ファイル**: `glreview/tui/widgets/content_panel.py`, `glreview/tui/app.py`

---

## 概要

差分ビューで次/前の変更行 (`+` 追加行 / `-` 削除行) へ直接カーソルを移動するアクションとフッターボタンを追加する。

---

## キーバインド

### 新規追加（ContentPanel）

| キー | アクション | 説明 |
|------|-----------|------|
| `]`  | `jump_next_diff_line` | 次の変更行 (add/rem) へジャンプ |
| `[`  | `jump_prev_diff_line` | 前の変更行 (add/rem) へジャンプ |

- 両バインドは `priority=True` を付与し、アプリレベルの `[` バインドを ContentPanel フォーカス時に上書きする。
- フッターへの自動表示のため `show=True`（デフォルト）のまま。

### 変更（app.py）

| 変更前 | 変更後 | アクション |
|--------|--------|-----------|
| `left_square_bracket` | `backslash` | `toggle_sidebar` |

- ContentPanel 以外のフォーカス状態での `[` 衝突を防ぐため変更。

---

## 実装詳細

### 新規インスタンス変数

`ContentPanel.__init__` に追加:

```python
self._diff_row_types: list[str] = []
```

各テーブル行に対応する差分行タイプ (`"add"`, `"rem"`, `"ctx"`, `"gap"`, `"hunk"` 等) を保持する。

### _render_diff() の変更

`rows = self._build_augmented_rows()` の直後に記録:

```python
self._diff_row_types = [t for t, *_ in rows]
```

`_render_unified_table` / `_render_sbs_tables` には変更不要。

### clear_content() の変更

リセット処理に追加:

```python
self._diff_row_types = []
```

### 新規アクション

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

---

## 動作仕様

- 差分ビュー (`ContentViewState.DIFF`) のみ有効。Overview・空状態では無操作。
- Unified / Side-by-side 両モード対応。`_focused_diff_table()` で対象テーブルを自動判定。
- 次/前がない場合（末尾/先頭）は何もしない（エラーなし）。
- `_diff_row_types` は `_render_diff` 呼び出し（ファイル切り替え・再描画）のたびに更新される。

---

## 変更ファイル一覧

| ファイル | 変更内容 |
|----------|---------|
| `glreview/tui/widgets/content_panel.py` | `BINDINGS` 追加、`__init__` 変数追加、`_render_diff` 型記録、`clear_content` リセット、アクション2件追加 |
| `glreview/tui/app.py` | `toggle_sidebar` のキーを `backslash` に変更 |
