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
