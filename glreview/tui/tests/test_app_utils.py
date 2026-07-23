"""tui/app.py のユーティリティ関数テスト。"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from glreview.tui.app import _resolve_terminal_cmd


class TestResolveTerminalCmd:
    def test_explicit_config_found(self) -> None:
        with patch("shutil.which", return_value="/usr/bin/xterm"):
            result = _resolve_terminal_cmd("xterm -e")
        assert result == ["xterm", "-e"]

    def test_explicit_config_not_found(self) -> None:
        with patch("shutil.which", return_value=None):
            result = _resolve_terminal_cmd("nonexistent-term -e")
        assert result is None

    def test_env_terminal_used_when_no_config(self, monkeypatch) -> None:
        monkeypatch.setattr(os, "name", "posix")
        monkeypatch.setenv("TERMINAL", "xterm")
        with patch("shutil.which", return_value="/usr/bin/xterm"):
            result = _resolve_terminal_cmd("")
        assert result is not None
        assert "xterm" in result[0]

    def test_env_terminal_not_found_fallback_to_candidates(self, monkeypatch) -> None:
        monkeypatch.setattr(os, "name", "posix")
        monkeypatch.setenv("TERMINAL", "nonexistent-term")

        def which_side_effect(cmd):
            # TERMINAL が見つからず、候補でのみ "xterm" が見つかる
            if cmd == "nonexistent-term":
                return None
            if cmd == "xterm":
                return "/usr/bin/xterm"
            return None

        with patch("shutil.which", side_effect=which_side_effect):
            result = _resolve_terminal_cmd("")
        assert result is not None
        assert result[0] == "xterm"

    def test_no_env_terminal_finds_candidate(self, monkeypatch) -> None:
        monkeypatch.setattr(os, "name", "posix")
        monkeypatch.delenv("TERMINAL", raising=False)

        def which_side_effect(cmd):
            if cmd == "kitty":
                return "/usr/bin/kitty"
            return None

        with patch("shutil.which", side_effect=which_side_effect):
            result = _resolve_terminal_cmd("")
        assert result is not None
        assert result[0] == "kitty"

    def test_no_terminal_found_returns_none(self, monkeypatch) -> None:
        monkeypatch.setattr(os, "name", "posix")
        monkeypatch.delenv("TERMINAL", raising=False)
        with patch("shutil.which", return_value=None):
            result = _resolve_terminal_cmd("")
        assert result is None


@pytest.mark.asyncio
async def test_content_panel_set_methods() -> None:
    """ContentPanel の setter メソッドが正常に動作することを確認する。"""

    from textual.app import App, ComposeResult

    from glreview.tui.widgets.content_panel import ContentPanel

    class _TestApp(App):
        def compose(self) -> ComposeResult:
            yield ContentPanel(MagicMock(), MagicMock())

    test_app = _TestApp()
    async with test_app.run_test() as _:
        panel = test_app.query_one(ContentPanel)

        # set_editor_command
        panel.set_editor_command("nvim")
        assert panel._editor_command == "nvim"

        # set_pygments_style with valid style
        panel.set_pygments_style("monokai")
        assert panel._pygments_style == "monokai"

        # set_pygments_style with empty string resets to defaults
        panel.set_pygments_style("")
        assert panel._pygments_style == ""

        # set_style_save_callback
        callback = MagicMock()
        panel.set_style_save_callback(callback)
        assert panel._on_style_saved is callback


@pytest.mark.asyncio
async def test_diff_gutter_set_rows() -> None:
    """DiffGutter の set_rows が行タイプリストを設定することを確認する。"""
    from textual.app import App, ComposeResult

    from glreview.tui.widgets._diff_renderer import DiffGutter

    class _TestApp(App):
        def compose(self) -> ComposeResult:
            yield DiffGutter(id="test-gutter")

    test_app = _TestApp()
    async with test_app.run_test() as _:
        gutter = test_app.query_one(DiffGutter)
        gutter.set_rows(["ctx", "add", "rem", "hunk", "ctx"])
        assert gutter._row_types == ["ctx", "add", "rem", "hunk", "ctx"]


@pytest.mark.asyncio
async def test_content_panel_show_overview_with_mocked_services() -> None:
    """ShowOverview メッセージを送信するとoverview が表示されることを確認する。"""
    from unittest.mock import AsyncMock

    from textual.app import App, ComposeResult

    from glreview.models import MergeRequestDetail
    from glreview.tui.messages import ShowOverview
    from glreview.tui.widgets.content_panel import ContentPanel

    mr_detail = MergeRequestDetail(
        iid=1,
        title="Test MR",
        description="Test description",
        author="alice",
        status="opened",
        labels=[],
        web_url="https://gitlab.example.com/mr/1",
        created_at="2026-01-01",
        updated_at="2026-01-02",
    )
    mock_mr_service = MagicMock()
    mock_mr_service.get_mr_detail = AsyncMock(return_value=mr_detail)
    mock_comment_service = MagicMock()
    mock_comment_service.get_discussions = AsyncMock(return_value=[])
    mock_comment_service.get_draft_notes = AsyncMock(return_value=[])

    class _TestApp(App):
        def compose(self) -> ComposeResult:
            yield ContentPanel(mock_mr_service, mock_comment_service)

    test_app = _TestApp()
    async with test_app.run_test() as pilot:
        panel = test_app.query_one(ContentPanel)
        panel.post_message(ShowOverview(mr_iid=1))
        await pilot.pause(0.5)
        # overview がロードされたことを確認
        from glreview.tui.entities import ContentViewState

        assert panel._view_state == ContentViewState.OVERVIEW


@pytest.mark.asyncio
async def test_content_panel_query_methods_when_empty() -> None:
    """ContentPanel のクエリメソッドが空状態で None を返すことを確認する。"""

    from textual.app import App, ComposeResult

    from glreview.tui.widgets.content_panel import ContentPanel

    class _TestApp(App):
        def compose(self) -> ComposeResult:
            yield ContentPanel(MagicMock(), MagicMock())

    test_app = _TestApp()
    async with test_app.run_test() as _:
        panel = test_app.query_one(ContentPanel)
        assert panel.get_current_file_path() is None
        assert panel.get_selected_line() is None


@pytest.mark.asyncio
async def test_content_panel_query_methods_when_diff_loaded() -> None:
    """ContentPanel がdiff表示中にクエリメソッドが正しい値を返すことを確認する。"""
    from unittest.mock import AsyncMock

    from textual.app import App, ComposeResult

    from glreview.models import FileDiff
    from glreview.tui.messages import ShowDiff
    from glreview.tui.widgets.content_panel import ContentPanel

    file_diff = FileDiff(
        file_path="src/main.py",
        diff="@@ -1,2 +1,2 @@\n context\n-old\n+new\n",
        old_path="src/main.py",
        new_path="src/main.py",
    )
    mock_mr_service = MagicMock()
    mock_mr_service.get_mr_diff = AsyncMock(return_value=file_diff)
    mock_comment_service = MagicMock()
    mock_comment_service.get_discussions = AsyncMock(return_value=[])
    mock_comment_service.get_draft_notes = AsyncMock(return_value=[])

    class _TestApp(App):
        def compose(self) -> ComposeResult:
            yield ContentPanel(mock_mr_service, mock_comment_service)

    test_app = _TestApp()
    async with test_app.run_test() as pilot:
        panel = test_app.query_one(ContentPanel)
        panel.post_message(ShowDiff(mr_iid=1, file_path="src/main.py"))
        await pilot.pause(0.5)

        assert panel.get_current_file_path() == "src/main.py"
        result = panel.get_selected_line()
        assert result is not None


@pytest.mark.asyncio
async def test_content_panel_toggle_wrap_when_diff_loaded() -> None:
    """差分表示中に 'w' キーで折り返しが切り替わることを確認する。"""
    from unittest.mock import AsyncMock

    from textual.app import App, ComposeResult

    from glreview.models import FileDiff
    from glreview.tui.messages import ShowDiff
    from glreview.tui.widgets.content_panel import ContentPanel

    file_diff = FileDiff(
        file_path="wrap_test.py",
        diff="@@ -1,2 +1,2 @@\n context\n-old\n+new\n",
        old_path="wrap_test.py",
        new_path="wrap_test.py",
    )
    mock_mr_service = MagicMock()
    mock_mr_service.get_mr_diff = AsyncMock(return_value=file_diff)
    mock_comment_service = MagicMock()
    mock_comment_service.get_discussions = AsyncMock(return_value=[])
    mock_comment_service.get_draft_notes = AsyncMock(return_value=[])

    class _TestApp(App):
        def compose(self) -> ComposeResult:
            yield ContentPanel(mock_mr_service, mock_comment_service)

    test_app = _TestApp()
    async with test_app.run_test() as pilot:
        panel = test_app.query_one(ContentPanel)
        panel.post_message(ShowDiff(mr_iid=1, file_path="wrap_test.py"))
        await pilot.pause(0.5)

        initial_wrap = panel._wrap_lines
        await pilot.press("w")
        assert panel._wrap_lines != initial_wrap


@pytest.mark.asyncio
async def test_content_panel_toggle_diff_mode_when_diff_loaded() -> None:
    """差分表示中に 't' キーで表示モードが切り替わることを確認する。"""
    from unittest.mock import AsyncMock

    from textual.app import App, ComposeResult

    from glreview.models import FileDiff
    from glreview.tui.entities import DiffViewMode
    from glreview.tui.messages import ShowDiff
    from glreview.tui.widgets.content_panel import ContentPanel

    file_diff = FileDiff(
        file_path="toggle_test.py",
        diff="@@ -1,2 +1,2 @@\n context\n-old\n+new\n",
        old_path="toggle_test.py",
        new_path="toggle_test.py",
    )
    mock_mr_service = MagicMock()
    mock_mr_service.get_mr_diff = AsyncMock(return_value=file_diff)
    mock_comment_service = MagicMock()
    mock_comment_service.get_discussions = AsyncMock(return_value=[])
    mock_comment_service.get_draft_notes = AsyncMock(return_value=[])

    class _TestApp(App):
        def compose(self) -> ComposeResult:
            yield ContentPanel(mock_mr_service, mock_comment_service)

    test_app = _TestApp()
    async with test_app.run_test() as pilot:
        panel = test_app.query_one(ContentPanel)
        panel.post_message(ShowDiff(mr_iid=1, file_path="toggle_test.py"))
        await pilot.pause(0.5)

        assert panel._diff_mode == DiffViewMode.UNIFIED
        await pilot.press("t")
        await pilot.pause(0.5)
        assert panel._diff_mode == DiffViewMode.SIDE_BY_SIDE


@pytest.mark.asyncio
async def test_content_panel_select_syntax_dialog_opens_when_diff() -> None:
    """差分表示中に 's' キーで SyntaxSelectDialog が開くことを確認する。"""
    from unittest.mock import AsyncMock

    from textual.app import App, ComposeResult

    from glreview.models import FileDiff
    from glreview.tui.messages import ShowDiff
    from glreview.tui.screens.syntax_select_dialog import SyntaxSelectDialog
    from glreview.tui.widgets.content_panel import ContentPanel

    file_diff = FileDiff(
        file_path="syntax_test.py",
        diff="@@ -1,2 +1,2 @@\n context\n-old\n+new\n",
        old_path="syntax_test.py",
        new_path="syntax_test.py",
    )
    mock_mr_service = MagicMock()
    mock_mr_service.get_mr_diff = AsyncMock(return_value=file_diff)
    mock_comment_service = MagicMock()
    mock_comment_service.get_discussions = AsyncMock(return_value=[])
    mock_comment_service.get_draft_notes = AsyncMock(return_value=[])

    class _TestApp(App):
        def compose(self) -> ComposeResult:
            yield ContentPanel(mock_mr_service, mock_comment_service)

    test_app = _TestApp()
    async with test_app.run_test() as pilot:
        panel = test_app.query_one(ContentPanel)
        panel.post_message(ShowDiff(mr_iid=1, file_path="syntax_test.py"))
        await pilot.pause(0.5)
        await pilot.press("s")
        assert isinstance(test_app.screen, SyntaxSelectDialog)
        await pilot.press("escape")


@pytest.mark.asyncio
async def test_content_panel_select_style_dialog_opens_when_diff() -> None:
    """差分表示中に 'p' キーで StyleSelectDialog が開くことを確認する。"""
    from unittest.mock import AsyncMock

    from textual.app import App, ComposeResult

    from glreview.models import FileDiff
    from glreview.tui.messages import ShowDiff
    from glreview.tui.screens.style_select_dialog import StyleSelectDialog
    from glreview.tui.widgets.content_panel import ContentPanel

    file_diff = FileDiff(
        file_path="style_test.py",
        diff="@@ -1,2 +1,2 @@\n context\n-old\n+new\n",
        old_path="style_test.py",
        new_path="style_test.py",
    )
    mock_mr_service = MagicMock()
    mock_mr_service.get_mr_diff = AsyncMock(return_value=file_diff)
    mock_comment_service = MagicMock()
    mock_comment_service.get_discussions = AsyncMock(return_value=[])
    mock_comment_service.get_draft_notes = AsyncMock(return_value=[])

    class _TestApp(App):
        def compose(self) -> ComposeResult:
            yield ContentPanel(mock_mr_service, mock_comment_service)

    test_app = _TestApp()
    async with test_app.run_test() as pilot:
        panel = test_app.query_one(ContentPanel)
        panel.post_message(ShowDiff(mr_iid=1, file_path="style_test.py"))
        await pilot.pause(0.5)
        await pilot.press("p")
        assert isinstance(test_app.screen, StyleSelectDialog)
        await pilot.press("escape")


@pytest.mark.asyncio
async def test_content_panel_show_diff_with_mocked_services() -> None:
    """ShowDiff メッセージを送信すると差分が表示されることを確認する。"""
    from unittest.mock import AsyncMock

    from textual.app import App, ComposeResult

    from glreview.models import FileDiff
    from glreview.tui.messages import ShowDiff
    from glreview.tui.widgets.content_panel import ContentPanel

    file_diff = FileDiff(
        file_path="foo.py",
        diff="@@ -1,3 +1,3 @@\n context\n-old\n+new\n context\n",
        old_path="foo.py",
        new_path="foo.py",
    )
    mock_mr_service = MagicMock()
    mock_mr_service.get_mr_diff = AsyncMock(return_value=file_diff)
    mock_comment_service = MagicMock()
    mock_comment_service.get_discussions = AsyncMock(return_value=[])
    mock_comment_service.get_draft_notes = AsyncMock(return_value=[])

    class _TestApp(App):
        def compose(self) -> ComposeResult:
            yield ContentPanel(mock_mr_service, mock_comment_service)

    test_app = _TestApp()
    async with test_app.run_test() as pilot:
        panel = test_app.query_one(ContentPanel)
        panel.post_message(ShowDiff(mr_iid=1, file_path="foo.py"))
        await pilot.pause(0.5)
        from glreview.tui.entities import ContentViewState

        assert panel._view_state == ContentViewState.DIFF
