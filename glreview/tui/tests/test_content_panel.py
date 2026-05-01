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


@pytest.mark.asyncio
async def test_diff_row_types_reset_on_clear_content() -> None:
    """`clear_content()` 後に `_diff_row_types` がリセットされることを確認する。"""
    panel = _make_panel()
    panel._diff_row_types = ["add", "ctx", "rem"]

    # clear_content は Textual の DOM にアクセスするためモックする
    mock_log = MagicMock()
    mock_table = MagicMock()

    def _query_one(selector, *args):
        from textual.widgets import RichLog

        if selector is RichLog or selector == RichLog:
            return mock_log
        return mock_table

    with patch.object(panel, "query_one", side_effect=_query_one):
        await panel.clear_content()

    assert panel._diff_row_types == []


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
