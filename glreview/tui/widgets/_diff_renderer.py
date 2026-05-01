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
