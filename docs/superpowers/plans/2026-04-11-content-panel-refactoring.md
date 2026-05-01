# content_panel.py リファクタリング 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `content_panel.py`（1870行）を責務ごとに5ファイルへ分割し、各モジュールを独立して理解・テスト・修正できるようにする。

**Architecture:** Martin Fowler の Extract Module / Move Function 手法を適用。`_diff_parser.py`・`_syntax.py`・`_overview.py`・`_diff_renderer.py` の4サブモジュールを作成し、`content_panel.py` は `ContentPanel` クラスのみを残すコーディネータとする。各タスク後にテストが通ることを確認しながら段階的に進める。

**Tech Stack:** Python 3.11+, Textual, Pygments, Rich, pytest, pytest-asyncio

---

## ファイル構成

| 操作 | ファイル |
|------|---------|
| 作成 | `glreview/tui/widgets/_diff_parser.py` |
| 作成 | `glreview/tui/widgets/_syntax.py` |
| 作成 | `glreview/tui/widgets/_overview.py` |
| 作成 | `glreview/tui/widgets/_diff_renderer.py` |
| 修正 | `glreview/tui/widgets/content_panel.py` |
| 修正 | `glreview/tui/tests/test_entities.py` |
| 修正 | `glreview/tui/tests/test_app_utils.py` |

---

## Task 1: `_diff_parser.py` を作成する

unified diff のパース・フィルタリング専用モジュール。

**Files:**
- Create: `glreview/tui/widgets/_diff_parser.py`
- Modify: `glreview/tui/widgets/content_panel.py`
- Modify: `glreview/tui/tests/test_entities.py`

- [ ] **Step 1: `_diff_parser.py` を新規作成する**

`glreview/tui/widgets/_diff_parser.py` を以下の内容で作成する:

```python
"""unified diff パース・フィルタリング関数。"""

from __future__ import annotations

import re

# ±コンテキスト行数（デフォルト表示する変更行前後の行数）
_CONTEXT_LINES = 5

# top/bottom ロード行のギャップ範囲センチネル値
_TOP_LOAD_SENTINEL = (-1, -1)
_BOTTOM_LOAD_SENTINEL = (-2, -2)

# 一度に追加読み込みする行数
_LOAD_MORE_LINES = 10


def _parse_diff(diff_text: str) -> list[tuple[str, int | None, int | None, str]]:
    """unified diff を解析してタプルリストを返す。

    Returns:
        list of (line_type, old_no, new_no, text)
        line_type: "hunk" | "header" | "add" | "rem" | "ctx"
    """
    parsed: list[tuple[str, int | None, int | None, str]] = []
    old_no = new_no = 0
    for line in diff_text.splitlines():
        if line.startswith("@@"):
            m = re.search(r"-(\d+)(?:,\d+)? \+(\d+)(?:,\d+)?", line)
            if m:
                old_no = int(m.group(1)) - 1
                new_no = int(m.group(2)) - 1
            parsed.append(("hunk", None, None, line))
        elif line.startswith("---") or line.startswith("+++"):
            parsed.append(("header", None, None, line))
        elif line.startswith("+"):
            new_no += 1
            parsed.append(("add", None, new_no, line))
        elif line.startswith("-"):
            old_no += 1
            parsed.append(("rem", old_no, None, line))
        else:
            old_no += 1
            new_no += 1
            parsed.append(("ctx", old_no, new_no, line))
    return parsed


def _apply_context_filter(
    parsed: list[tuple[str, int | None, int | None, str]],
    context: int,
    forced_ctx_indices: set[int] | None = None,
) -> list[tuple[str, int | None, int | None, str]]:
    """コンテキスト行を ±context 行に制限し、隠れた行を "gap" エントリに置換する。

    gap エントリのフォーマット: ("gap", gap_start_idx, gap_end_idx, text)
    gap_start_idx / gap_end_idx は parsed リスト内のインデックス。
    forced_ctx_indices に含まれるインデックスの ctx 行は強制的に表示する。
    """
    forced = forced_ctx_indices or set()
    changes = {i for i, (t, *_) in enumerate(parsed) if t in ("add", "rem")}

    def _keep(i: int, t: str) -> bool:
        if t != "ctx":
            return True
        return any(abs(i - c) <= context for c in changes) or i in forced

    result: list[tuple[str, int | None, int | None, str]] = []
    i = 0
    while i < len(parsed):
        t = parsed[i][0]
        if not _keep(i, t):
            gap_start = i
            gap = 0
            while i < len(parsed) and not _keep(i, parsed[i][0]):
                gap += 1
                i += 1
            gap_end = i - 1
            result.append(("gap", gap_start, gap_end, f"··· {gap} lines hidden ···"))
        else:
            result.append(parsed[i])
            i += 1
    return result


def _find_first_last_new_line(
    parsed: list[tuple[str, int | None, int | None, str]],
) -> tuple[int, int]:
    """パース済み diff の新ファイル側の最初と最後の行番号を返す (0 = 未検出)。"""
    first = last = 0
    for _, _, new_n, _ in parsed:
        if new_n is not None:
            if first == 0:
                first = new_n
            last = new_n
    return first, last
```

- [ ] **Step 2: `content_panel.py` から移動した定数・関数を削除し、新モジュールからインポートする**

`content_panel.py` の既存インポートブロックの末尾（`SyntaxSelectDialog,` の行の直後）に以下を追加する:

```python
from glreview.tui.widgets._diff_parser import (
    _CONTEXT_LINES,
    _LOAD_MORE_LINES,
    _TOP_LOAD_SENTINEL,
    _BOTTOM_LOAD_SENTINEL,
    _parse_diff,
    _apply_context_filter,
    _find_first_last_new_line,
)
```

次に `content_panel.py` から以下の定数定義を削除する（`_logger = get_logger(__name__)` の行の前後にある）:

```python
# ±コンテキスト行数（デフォルト表示する変更行前後の行数）
_CONTEXT_LINES = 5

# 行番号列の幅（最大4桁 + 💬マーカー(2セル) = 6）
_LINE_NO_WIDTH = 6

# top/bottom ロード行のギャップ範囲センチネル値
_TOP_LOAD_SENTINEL = (-1, -1)
_BOTTOM_LOAD_SENTINEL = (-2, -2)

# 一度に追加読み込みする行数
_LOAD_MORE_LINES = 10
```

→ `_LINE_NO_WIDTH` は Task 4 で移動するため、この時点では残す。削除するのは `_CONTEXT_LINES`・`_TOP_LOAD_SENTINEL`・`_BOTTOM_LOAD_SENTINEL`・`_LOAD_MORE_LINES` の4定数のみ。

次に `content_panel.py` から以下の3関数を削除する（各関数の docstring と本体ごと削除）:

- `_parse_diff` 関数（`def _parse_diff(diff_text: str)` から始まる約30行）
- `_apply_context_filter` 関数（`def _apply_context_filter(` から始まる約35行）
- `_find_first_last_new_line` 関数（`def _find_first_last_new_line(` から始まる約10行）

- [ ] **Step 3: `test_entities.py` の in-function インポートを更新する**

`test_entities.py` 内の以下のインポートをすべて置換する（関数内インポートのみ対象、`replace_all=true` で一括置換）:

| 変更前 | 変更後 |
|--------|--------|
| `from glreview.tui.widgets.content_panel import _parse_diff` | `from glreview.tui.widgets._diff_parser import _parse_diff` |
| `from glreview.tui.widgets.content_panel import _apply_context_filter, _parse_diff` | `from glreview.tui.widgets._diff_parser import _apply_context_filter, _parse_diff` |
| `from glreview.tui.widgets.content_panel import _find_first_last_new_line, _parse_diff` | `from glreview.tui.widgets._diff_parser import _find_first_last_new_line, _parse_diff` |
| `from glreview.tui.widgets.content_panel import _find_first_last_new_line` | `from glreview.tui.widgets._diff_parser import _find_first_last_new_line` |

対象行: 461, 469, 476, 487, 501, 510, 555, 581, 592

- [ ] **Step 4: テストを実行してグリーンを確認する**

```bash
python -m pytest glreview/tui/tests/ -v
```

期待結果: すべてのテストが PASSED

- [ ] **Step 5: コミットする**

```bash
git add glreview/tui/widgets/_diff_parser.py glreview/tui/widgets/content_panel.py glreview/tui/tests/test_entities.py
git commit -m "refactor: diff パース・フィルタ関数を _diff_parser.py に抽出する"
```

---

## Task 2: `_syntax.py` を作成する

Pygments シンタックスハイライト専用モジュール。

**Files:**
- Create: `glreview/tui/widgets/_syntax.py`
- Modify: `glreview/tui/widgets/content_panel.py`
- Modify: `glreview/tui/tests/test_entities.py`

- [ ] **Step 1: `_syntax.py` を新規作成する**

`glreview/tui/widgets/_syntax.py` を以下の内容で作成する:

```python
"""シンタックスハイライト（Pygments 連携）。"""

from __future__ import annotations

from typing import Any

from pygments.lexers import get_lexer_for_filename as _get_lexer_for_filename
from pygments.token import Token as _Token
from pygments.util import ClassNotFound as _ClassNotFound

# シンタックスハイライト用カラーマッピング（Dracula テーマ準拠）
_SYNTAX_COLORS: dict[Any, str] = {
    _Token.Keyword: "bold #ff79c6",
    _Token.Keyword.Constant: "#bd93f9",
    _Token.Keyword.Type: "#8be9fd",
    _Token.Keyword.Namespace: "bold #ff79c6",
    _Token.String: "#f1fa8c",
    _Token.String.Escape: "#ff79c6",
    _Token.String.Interpol: "#ff79c6",
    _Token.String.Doc: "#6272a4",
    _Token.Comment: "#6272a4",
    _Token.Name.Builtin: "#8be9fd",
    _Token.Name.Function: "#50fa7b",
    _Token.Name.Function.Magic: "#50fa7b",
    _Token.Name.Class: "#8be9fd",
    _Token.Name.Decorator: "#50fa7b",
    _Token.Name.Exception: "#ff5555",
    _Token.Name.Constant: "#bd93f9",
    _Token.Name.Namespace: "#8be9fd",
    _Token.Name.Attribute: "#50fa7b",
    _Token.Literal.Number: "#bd93f9",
    _Token.Operator: "#ff79c6",
    _Token.Operator.Word: "bold #ff79c6",
    _Token.Punctuation: "#f8f8f2",
    _Token.Generic.Deleted: "#ff5555",
    _Token.Generic.Inserted: "#50fa7b",
    _Token.Generic.Heading: "bold #f8f8f2",
}


def _build_colors_from_pygments_style(style_name: str) -> dict[Any, str]:
    """Pygments 組み込みスタイルから Rich スタイル文字列マップを構築する。

    変換できない場合は空 dict を返す（呼び出し元が _SYNTAX_COLORS にフォールバック）。
    """
    try:
        from pygments.styles import get_style_by_name

        style_cls = get_style_by_name(style_name)
        colors: dict[Any, str] = {}
        for token, style_def in style_cls:
            parts: list[str] = []
            if style_def["bold"]:
                parts.append("bold")
            if style_def["italic"]:
                parts.append("italic")
            if style_def["color"]:
                parts.append(f"#{style_def['color']}")
            if parts:
                colors[token] = " ".join(parts)
        return colors
    except Exception:
        return {}


def _get_lexer_for_path(file_path: str | None) -> Any | None:
    """ファイルパスから Pygments レキサーを返す。対応言語なければ None。"""
    if not file_path:
        return None
    try:
        return _get_lexer_for_filename(file_path, stripnl=True)
    except _ClassNotFound:
        return None


def _get_token_color(token_type: Any) -> str | None:
    """Pygments トークンタイプを親クラスまで辿り、Rich スタイル文字列を返す。"""
    t = token_type
    while t is not None:
        color = _SYNTAX_COLORS.get(t)
        if color is not None:
            return color
        parent = t.parent
        if parent is t:
            break
        t = parent
    return None
```

- [ ] **Step 2: `content_panel.py` を更新する**

`content_panel.py` のインポートブロックに以下を追加する（`_diff_parser` インポートの直後）:

```python
from glreview.tui.widgets._syntax import (
    _SYNTAX_COLORS,
    _build_colors_from_pygments_style,
    _get_lexer_for_path,
)
```

`content_panel.py` の既存インポートから以下の3行を削除する:

```python
from pygments.lexers import get_lexer_for_filename as _get_lexer_for_filename
from pygments.token import Token as _Token
from pygments.util import ClassNotFound as _ClassNotFound
```

`content_panel.py` から以下のコードブロックを削除する（`_logger = get_logger(__name__)` の前にある）:

- `# シンタックスハイライト用カラーマッピング（Dracula テーマ準拠）` コメントと `_SYNTAX_COLORS` 辞書定義（約30行）
- `_build_colors_from_pygments_style` 関数（約25行）
- `_get_lexer_for_path` 関数（約10行）
- モジュールレベルの `_get_token_color` 関数（約12行）

  ⚠️ `ContentPanel` クラス内のインスタンスメソッド `_get_token_color`（`self._syntax_colors` を使うもの）は削除しない。

- [ ] **Step 3: `test_entities.py` の in-function インポートを更新する**

以下の置換を `test_entities.py` に適用する（各行を該当モジュールへ更新）:

| 変更前 | 変更後 |
|--------|--------|
| `from glreview.tui.widgets.content_panel import _get_token_color` | `from glreview.tui.widgets._syntax import _get_token_color` |
| `from glreview.tui.widgets.content_panel import _get_lexer_for_path` | `from glreview.tui.widgets._syntax import _get_lexer_for_path` |
| `from glreview.tui.widgets.content_panel import _build_colors_from_pygments_style` | `from glreview.tui.widgets._syntax import _build_colors_from_pygments_style` |

対象行: 436, 444, 452, 519, 525, 531, 538, 544

- [ ] **Step 4: テストを実行してグリーンを確認する**

```bash
python -m pytest glreview/tui/tests/ -v
```

期待結果: すべてのテストが PASSED

- [ ] **Step 5: コミットする**

```bash
git add glreview/tui/widgets/_syntax.py glreview/tui/widgets/content_panel.py glreview/tui/tests/test_entities.py
git commit -m "refactor: シンタックスハイライト関数を _syntax.py に抽出する"
```

---

## Task 3: `_overview.py` を作成する

MR Overview 表示テキスト構築・コメント位置管理専用モジュール。

**Files:**
- Create: `glreview/tui/widgets/_overview.py`
- Modify: `glreview/tui/widgets/content_panel.py`
- Modify: `glreview/tui/tests/test_entities.py`

- [ ] **Step 1: `_overview.py` を新規作成する**

`glreview/tui/widgets/_overview.py` を以下の内容で作成する:

```python
"""MR Overview 表示テキスト構築・コメント位置管理。"""

from __future__ import annotations

import re

from glreview.models import Discussion

_IMAGE_PATTERN = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")


def _extract_images(text: str) -> list[tuple[str, str]]:
    """Markdownテキストから画像リンクを抽出して (alt, url) リストを返す。"""
    return _IMAGE_PATTERN.findall(text)


def _build_overview_text(mr_detail, discussions: list[Discussion]) -> str:
    """MR詳細とディスカッションからOverview表示テキストを構築する。"""
    lines: list[str] = []
    lines.append(f"# !{mr_detail.iid} {mr_detail.title}")
    lines.append("")
    lines.append("| Field      | Value                          |")
    lines.append("|------------|-------------------------------|")
    lines.append(f"| Author     | {mr_detail.author}            |")
    lines.append(f"| Assignee   | {mr_detail.assignee or '—'}   |")
    lines.append(f"| Status     | {mr_detail.status}            |")
    lines.append(f"| Labels     | {', '.join(mr_detail.labels) or '—'} |")
    lines.append(f"| Milestone  | {mr_detail.milestone or '—'}  |")
    lines.append(f"| Pipeline   | {mr_detail.pipeline_status or '—'} |")
    lines.append(f"| URL        | {mr_detail.web_url}           |")
    lines.append(f"| Created    | {mr_detail.created_at}        |")
    lines.append(f"| Updated    | {mr_detail.updated_at}        |")
    lines.append("")
    lines.append("## Description")
    lines.append("")
    lines.append(mr_detail.description or "(no description)")
    lines.append("")

    # 説明文・ディスカッション内の画像URLを収集して表示
    all_images: list[tuple[str, str]] = []
    if mr_detail.description:
        all_images.extend(_extract_images(mr_detail.description))
    for disc in discussions:
        for note in disc.notes:
            all_images.extend(_extract_images(note.body))
    if all_images:
        lines.append(f"## Images ({len(all_images)})")
        lines.append("")
        for alt, url in all_images:
            label = alt if alt else url
            lines.append(f"- [{label}]({url})")
        lines.append("")

    lines.append(f"## Discussions ({len(discussions)})")
    for disc in discussions:
        for i, note in enumerate(disc.notes):
            prefix = "  " if i > 0 else ""
            pos_info = ""
            if note.position is not None:
                line_no = note.position.new_line or note.position.old_line
                pos_info = f" [{note.position.file_path}:{line_no}]"
            lines.append(f"{prefix}**{note.author}**{pos_info} ({note.created_at})")
            for body_line in note.body.splitlines():
                lines.append(f"{prefix}  {body_line}")
            lines.append("")
    return "\n".join(lines)


def _get_comment_lines(discussions: list[Discussion], file_path: str) -> set[int]:
    """インラインコメントが付いている行番号の集合を返す。"""
    lines: set[int] = set()
    for disc in discussions:
        for note in disc.notes:
            if note.position is not None and note.position.file_path == file_path:
                if note.position.new_line is not None:
                    lines.add(note.position.new_line)
                elif note.position.old_line is not None:
                    lines.add(note.position.old_line)
    return lines


def _build_comment_map(
    discussions: list[Discussion], file_path: str
) -> dict[int, list[Discussion]]:
    """行番号 → ディスカッションリストのマップを構築する。"""
    result: dict[int, list[Discussion]] = {}
    for disc in discussions:
        for note in disc.notes:
            if note.position is not None and note.position.file_path == file_path:
                line_no = note.position.new_line or note.position.old_line
                if line_no is not None:
                    if line_no not in result:
                        result[line_no] = []
                    if disc not in result[line_no]:
                        result[line_no].append(disc)
    return result
```

- [ ] **Step 2: `content_panel.py` を更新する**

`content_panel.py` のインポートブロックに以下を追加する（`_syntax` インポートの直後）:

```python
from glreview.tui.widgets._overview import (
    _build_overview_text,
    _get_comment_lines,
    _build_comment_map,
)
```

`content_panel.py` から以下のコードブロックを削除する:

- `_IMAGE_PATTERN = re.compile(...)` の1行
- `_extract_images` 関数（約5行）
- `_build_overview_text` 関数（約50行）
- `_get_comment_lines` 関数（約12行）
- `_build_comment_map` 関数（約15行）

- [ ] **Step 3: `test_entities.py` の in-function インポートと top-level インポートを更新する**

in-function インポートの置換:

| 変更前 | 変更後 |
|--------|--------|
| `from glreview.tui.widgets.content_panel import _build_overview_text` | `from glreview.tui.widgets._overview import _build_overview_text` |
| `from glreview.tui.widgets.content_panel import _extract_images` | `from glreview.tui.widgets._overview import _extract_images` |
| `from glreview.tui.widgets.content_panel import _build_comment_map` | `from glreview.tui.widgets._overview import _build_comment_map` |

対象行: 217, 236, 254, 273, 300, 319, 347, 352, 358, 365, 373, 380, 396, 411

次に top-level インポート（line 15）を更新する。`_get_comment_lines` は `content_panel.py` から削除されたため、インポート元を変更する:

変更前:
```python
from glreview.tui.widgets.content_panel import _format_diff_line, _get_comment_lines
```

変更後:
```python
from glreview.tui.widgets.content_panel import _format_diff_line
from glreview.tui.widgets._overview import _get_comment_lines
```

- [ ] **Step 4: テストを実行してグリーンを確認する**

```bash
python -m pytest glreview/tui/tests/ -v
```

期待結果: すべてのテストが PASSED

- [ ] **Step 5: コミットする**

```bash
git add glreview/tui/widgets/_overview.py glreview/tui/widgets/content_panel.py glreview/tui/tests/test_entities.py
git commit -m "refactor: Overview・コメントヘルパーを _overview.py に抽出する"
```

---

## Task 4: `_diff_renderer.py` を作成する

diff 行スタイル定数・テキスト折り返し・`DiffGutter` ウィジェット専用モジュール。

**Files:**
- Create: `glreview/tui/widgets/_diff_renderer.py`
- Modify: `glreview/tui/widgets/content_panel.py`
- Modify: `glreview/tui/tests/test_entities.py`
- Modify: `glreview/tui/tests/test_app_utils.py`

- [ ] **Step 1: `_diff_renderer.py` を新規作成する**

`glreview/tui/widgets/_diff_renderer.py` を以下の内容で作成する:

```python
"""diff 表示定数・テキスト折り返し・DiffGutter ウィジェット。"""

from __future__ import annotations

from typing import Any

from rich.segment import Segment
from rich.style import Style
from textual.strip import Strip
from textual.widget import Widget

# diff 行スタイル（Rich markup / style 文字列）
_DIFF_ADD_STYLE = "on #1a3a1a"
_DIFF_REM_STYLE = "on #3a1a1a"
_DIFF_HUNK_STYLE = "bold #6688cc"
_DIFF_GAP_STYLE = "dim italic"

# 行番号列の幅（最大4桁 + 💬マーカー(2セル) = 6）
_LINE_NO_WIDTH = 6


def _format_diff_line(line: str) -> str:
    """差分の1行を Rich マークアップでフォーマットする（テスト用に保持）。"""
    if line.startswith("@@"):
        return f"[{_DIFF_HUNK_STYLE}]{line}[/]"
    if line.startswith("+") and not line.startswith("+++"):
        escaped = line.replace("[", r"\[")
        return f"[{_DIFF_ADD_STYLE}]{escaped}[/]"
    if line.startswith("-") and not line.startswith("---"):
        escaped = line.replace("[", r"\[")
        return f"[{_DIFF_REM_STYLE}]{escaped}[/]"
    return line.replace("[", r"\[")


def _wrap_text(text: str, width: int) -> str:
    """テキストを指定幅で折り返す（コード向け文字単位）。"""
    if len(text) <= width:
        return text
    return "\n".join(text[i : i + width] for i in range(0, len(text), width))


class DiffGutter(Widget):
    """差分行の位置をスクロールバー横に示すガタービジェット。

    差分全体の行タイプリスト（"add" / "rem" / "hunk" / その他）を受け取り、
    ウィジェット高さに比例してカラーマーカーをレンダリングする。
    """

    DEFAULT_CSS = """
    DiffGutter {
        width: 1;
        height: 100%;
        background: $panel-darken-1;
    }
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._row_types: list[str] = []

    def set_rows(self, row_types: list[str]) -> None:
        """差分行タイプリストをセットして再描画する。"""
        self._row_types = row_types
        self.refresh()

    def render_line(self, y: int) -> Strip:
        total = len(self._row_types)
        height = self.size.height
        if total == 0 or height == 0:
            return Strip([Segment(" ")])
        # このガター行が担当する差分行の範囲を求め、最優先のマークを選ぶ。
        # 1点参照だと圧縮時に add/rem が飛ばされるため範囲スキャンが必要。
        start = int(y * total / height)
        end = min(max(start + 1, int((y + 1) * total / height)), total)
        priority: dict[str, int] = {"rem": 0, "add": 1, "hunk": 2}
        mark = min(self._row_types[start:end], key=lambda t: priority.get(t, 3))
        if mark == "add":
            return Strip([Segment("▌", Style(color="#88cc88"))])
        if mark == "rem":
            return Strip([Segment("▌", Style(color="#cc8888"))])
        return Strip([Segment(" ")])
```

- [ ] **Step 2: `content_panel.py` を更新する**

`content_panel.py` のインポートブロックに以下を追加する（`_overview` インポートの直後）:

```python
from glreview.tui.widgets._diff_renderer import (
    _DIFF_ADD_STYLE,
    _DIFF_REM_STYLE,
    _DIFF_HUNK_STYLE,
    _DIFF_GAP_STYLE,
    _LINE_NO_WIDTH,
    _wrap_text,
    DiffGutter,
)
```

`content_panel.py` の既存インポートから以下の4行を削除する:

```python
from rich.segment import Segment
from rich.style import Style
from textual.strip import Strip
from textual.widget import Widget
```

`content_panel.py` から以下のコードブロックを削除する:

- `# diff 行スタイル（Rich markup / style 文字列）` コメントと `_DIFF_ADD_STYLE`・`_DIFF_REM_STYLE`・`_DIFF_HUNK_STYLE`・`_DIFF_GAP_STYLE` の4定数
- `# 行番号列の幅` コメントと `_LINE_NO_WIDTH` 定数
- `_format_diff_line` 関数（約12行）
- `_wrap_text` 関数（約7行）
- `DiffGutter` クラス全体（約45行）

- [ ] **Step 3: `test_entities.py` の in-function インポートと top-level インポートを更新する**

in-function インポートの置換:

| 変更前 | 変更後 |
|--------|--------|
| `from glreview.tui.widgets.content_panel import _wrap_text` | `from glreview.tui.widgets._diff_renderer import _wrap_text` |

対象行: 191, 196, 201, 209

top-level インポート（line 15 周辺）を更新する。`_format_diff_line` は `content_panel.py` から削除されたため:

変更前:
```python
from glreview.tui.widgets.content_panel import _format_diff_line
from glreview.tui.widgets._overview import _get_comment_lines
```

変更後:
```python
from glreview.tui.widgets._diff_renderer import _format_diff_line
from glreview.tui.widgets._overview import _get_comment_lines
```

- [ ] **Step 4: `test_app_utils.py` の `DiffGutter` インポートを更新する**

`test_app_utils.py` の line 106 を更新する:

変更前:
```python
from glreview.tui.widgets.content_panel import DiffGutter
```

変更後:
```python
from glreview.tui.widgets._diff_renderer import DiffGutter
```

- [ ] **Step 5: テストを実行してグリーンを確認する**

```bash
python -m pytest glreview/tui/tests/ -v
```

期待結果: すべてのテストが PASSED

- [ ] **Step 6: コミットする**

```bash
git add glreview/tui/widgets/_diff_renderer.py glreview/tui/widgets/content_panel.py glreview/tui/tests/test_entities.py glreview/tui/tests/test_app_utils.py
git commit -m "refactor: DiffGutter・diff表示定数・_wrap_text を _diff_renderer.py に抽出する"
```

---

## Task 5: 最終検証とクリーンアップ

**Files:**
- Verify: `glreview/tui/widgets/content_panel.py`

- [ ] **Step 1: `content_panel.py` の不要なインポートがないか確認する**

全タスク完了後、`content_panel.py` の先頭インポートが以下の状態になっていることを確認する:

```python
"""ContentPanel — 右ペインのコンテンツ表示ウィジェット。"""

from __future__ import annotations

import re
from typing import Any, ClassVar

from pygments import lex as _pygments_lex
from rich.markdown import Markdown as RichMarkdown
from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import DataTable, RichLog, Static

from glreview.infrastructure.logger import get_logger
from glreview.models import CommentContext, CommentType, Discussion
from glreview.services import CommentService, MRService
from glreview.services.exceptions import GLReviewAPIError
from glreview.tui.entities import ContentViewState, DiffViewMode
from glreview.tui.messages import CommentPosted, ShowDiff, ShowOverview
from glreview.tui.screens.comment_dialog import CommentDialog
from glreview.tui.screens.comment_view_dialog import CommentViewDialog
from glreview.tui.screens.error_dialog import ErrorDialog
from glreview.tui.screens.style_select_dialog import (
    DEFAULT_OPTION_ID as _STYLE_DEFAULT,
)
from glreview.tui.screens.style_select_dialog import (
    StyleSelectDialog,
)
from glreview.tui.screens.syntax_select_dialog import (
    AUTO_OPTION_ID as _SYNTAX_AUTO,
)
from glreview.tui.screens.syntax_select_dialog import (
    NONE_OPTION_ID as _SYNTAX_NONE,
)
from glreview.tui.screens.syntax_select_dialog import (
    SyntaxSelectDialog,
)
from glreview.tui.widgets._diff_parser import (
    _CONTEXT_LINES,
    _LOAD_MORE_LINES,
    _TOP_LOAD_SENTINEL,
    _BOTTOM_LOAD_SENTINEL,
    _parse_diff,
    _apply_context_filter,
    _find_first_last_new_line,
)
from glreview.tui.widgets._syntax import (
    _SYNTAX_COLORS,
    _build_colors_from_pygments_style,
    _get_lexer_for_path,
)
from glreview.tui.widgets._overview import (
    _build_overview_text,
    _get_comment_lines,
    _build_comment_map,
)
from glreview.tui.widgets._diff_renderer import (
    _DIFF_ADD_STYLE,
    _DIFF_REM_STYLE,
    _DIFF_HUNK_STYLE,
    _DIFF_GAP_STYLE,
    _LINE_NO_WIDTH,
    _wrap_text,
    DiffGutter,
)
```

残留しているモジュールレベルのコードは `_logger = get_logger(__name__)` の1行のみであることを確認する。その直後は `ContentPanel` クラスの定義が始まる。

- [ ] **Step 2: 全テストスイートを実行する**

```bash
python -m pytest glreview/tui/tests/ -v
```

期待結果: すべてのテストが PASSED

- [ ] **Step 3: ファイル行数を確認する**

```bash
wc -l glreview/tui/widgets/content_panel.py glreview/tui/widgets/_diff_parser.py glreview/tui/widgets/_syntax.py glreview/tui/widgets/_overview.py glreview/tui/widgets/_diff_renderer.py
```

各ファイルがおおむね以下の行数になっていることを確認する（大きくずれている場合は不要なコードが残っている可能性がある）:
- `content_panel.py`: ~560行
- `_diff_parser.py`: ~100行
- `_syntax.py`: ~90行
- `_overview.py`: ~90行
- `_diff_renderer.py`: ~80行

- [ ] **Step 4: 最終コミットする**

```bash
git add -A
git commit -m "refactor: content_panel.py を責務ごとに5ファイルへ分割する"
```
