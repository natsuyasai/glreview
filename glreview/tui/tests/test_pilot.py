"""Textual Pilot テスト — 基本ケースのヘッドレステスト。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from glreview.models import AppConfig
from glreview.services.types import PaginatedResult
from glreview.tui.app import GLReviewApp
from glreview.tui.screens.error_dialog import ErrorDialog
from glreview.tui.screens.help_screen import HelpScreen


def _make_config() -> AppConfig:
    return AppConfig(
        gitlab_url="https://gitlab.example.com",
        token="test-token",
        editor="vi",
    )


def _make_mock_services():
    """MRService と CommentService のモックを生成する。"""
    empty_result = PaginatedResult(items=[], has_next_page=False, next_page=None)

    mr_service = MagicMock()
    mr_service.load = AsyncMock()
    mr_service.get_assigned_to_me = AsyncMock(return_value=empty_result)
    mr_service.get_reviewer_is_me = AsyncMock(return_value=empty_result)
    mr_service.get_created_by_me = AsyncMock(return_value=empty_result)
    mr_service.get_unassigned = AsyncMock(return_value=empty_result)
    mr_service.get_assigned_to_others = AsyncMock(return_value=empty_result)
    mr_service.invalidate_cache = MagicMock()

    comment_service = MagicMock()
    comment_service.load = AsyncMock()
    comment_service.invalidate_cache = MagicMock()

    return mr_service, comment_service


@pytest.fixture
def mock_app():
    """GitLab接続をモックしたGLReviewAppインスタンスを生成するファクトリ。"""
    config = _make_config()
    app = GLReviewApp(config=config, initial_mr_id=None)
    return app


@pytest.mark.asyncio
async def test_app_quit():
    """q キーでアプリが終了することを確認する。"""
    config = _make_config()
    mr_service, comment_service = _make_mock_services()

    with (
        patch("glreview.tui.app.GitLabClient") as mock_client_cls,
        patch("glreview.tui.app.MRService", return_value=mr_service),
        patch("glreview.tui.app.CommentService", return_value=comment_service),
        patch("glreview.tui.app.GitRepoDetector") as mock_detector_cls,
    ):
        mock_client = MagicMock()
        mock_client.connect = AsyncMock()
        mock_client_cls.return_value = mock_client

        mock_detector = MagicMock()
        mock_detector.get_project_info.return_value = MagicMock(project_path="group/project")
        mock_detector_cls.return_value = mock_detector

        app = GLReviewApp(config=config, initial_mr_id=None)
        async with app.run_test() as pilot:
            await pilot.press("q")
            assert app.is_running is False


@pytest.mark.asyncio
async def test_help_screen_opens():
    """? キーで HelpScreen が表示されることを確認する。"""
    config = _make_config()
    mr_service, comment_service = _make_mock_services()

    with (
        patch("glreview.tui.app.GitLabClient") as mock_client_cls,
        patch("glreview.tui.app.MRService", return_value=mr_service),
        patch("glreview.tui.app.CommentService", return_value=comment_service),
        patch("glreview.tui.app.GitRepoDetector") as mock_detector_cls,
    ):
        mock_client = MagicMock()
        mock_client.connect = AsyncMock()
        mock_client_cls.return_value = mock_client

        mock_detector = MagicMock()
        mock_detector.get_project_info.return_value = MagicMock(project_path="group/project")
        mock_detector_cls.return_value = mock_detector

        app = GLReviewApp(config=config, initial_mr_id=None)
        async with app.run_test() as pilot:
            await pilot.press("question_mark")
            # HelpScreen がスタックに積まれていることを確認
            assert isinstance(app.screen, HelpScreen)
            # Escape で閉じる
            await pilot.press("escape")


@pytest.mark.asyncio
async def test_sidebar_toggle():
    """[ キーでサイドバーのトグルが動作することを確認する。"""
    config = _make_config()
    mr_service, comment_service = _make_mock_services()

    with (
        patch("glreview.tui.app.GitLabClient") as mock_client_cls,
        patch("glreview.tui.app.MRService", return_value=mr_service),
        patch("glreview.tui.app.CommentService", return_value=comment_service),
        patch("glreview.tui.app.GitRepoDetector") as mock_detector_cls,
    ):
        mock_client = MagicMock()
        mock_client.connect = AsyncMock()
        mock_client_cls.return_value = mock_client

        mock_detector = MagicMock()
        mock_detector.get_project_info.return_value = MagicMock(project_path="group/project")
        mock_detector_cls.return_value = mock_detector

        app = GLReviewApp(config=config, initial_mr_id=None)
        async with app.run_test() as pilot:
            assert app._sidebar_visible is True
            await pilot.press("backslash")
            assert app._sidebar_visible is False
            await pilot.press("backslash")
            assert app._sidebar_visible is True


@pytest.mark.asyncio
async def test_error_dialog_shows_on_connection_failure():
    """GitLab接続失敗時にErrorDialogが表示されることを確認する。"""
    from glreview.services.exceptions import GitLabConnectionError

    config = _make_config()

    with (
        patch("glreview.tui.app.GitLabClient") as mock_client_cls,
        patch("glreview.tui.app.GitRepoDetector") as mock_detector_cls,
    ):
        mock_client = MagicMock()
        mock_client.connect = AsyncMock(side_effect=GitLabConnectionError("Connection failed"))
        mock_client_cls.return_value = mock_client

        mock_detector = MagicMock()
        mock_detector.get_project_info.return_value = MagicMock(project_path="group/project")
        mock_detector_cls.return_value = mock_detector

        app = GLReviewApp(config=config, initial_mr_id=None)
        async with app.run_test() as pilot:
            # ErrorDialog がスタックに積まれていることを確認
            assert isinstance(app.screen, ErrorDialog)
            # OK ボタンで閉じる
            await pilot.press("enter")


@pytest.mark.asyncio
async def test_error_dialog_dismiss():
    """ErrorDialogが表示され、Enterキーで閉じることができることを確認する。"""
    from textual.app import App, ComposeResult
    from textual.widgets import Label

    # Textual の on_mount はMRO全体で呼ばれるため、GLReviewAppを継承せず
    # 独立した App クラスでテストする
    class _TestApp(App):
        def compose(self) -> ComposeResult:
            yield Label("base")

        async def on_mount(self) -> None:
            await self.push_screen(ErrorDialog("Test error message"))

    test_app = _TestApp()
    async with test_app.run_test() as pilot:
        assert isinstance(test_app.screen, ErrorDialog)
        await pilot.press("enter")
        # ErrorDialog が閉じられていることを確認（メインスクリーンに戻る）
        assert not isinstance(test_app.screen, ErrorDialog)


def test_c_key_binding_has_priority():
    """ContentPanel の c バインディングが priority=True であることを確認する。"""
    from glreview.tui.widgets.content_panel import ContentPanel

    bindings = {b.key: b for b in ContentPanel.BINDINGS}
    assert "c" in bindings
    assert bindings["c"].priority is True


def test_e_key_binding_has_priority():
    """App の e バインディングが priority=True であることを確認する。"""
    from glreview.tui.app import GLReviewApp

    bindings = {b.key: b for b in GLReviewApp.BINDINGS}
    assert "e" in bindings
    assert bindings["e"].priority is True


def test_content_panel_wrap_lines_default():
    """ContentPanel の _wrap_lines が初期値 False であることを確認する。"""
    from glreview.tui.widgets.content_panel import ContentPanel

    panel = ContentPanel(MagicMock(), MagicMock())
    assert panel._wrap_lines is False


def test_comment_dialog_has_container():
    """CommentDialog の compose が #dialog-container Vertical を含むことを確認する。"""
    import inspect

    from glreview.models import CommentContext, CommentType
    from glreview.tui.screens.comment_dialog import CommentDialog

    context = CommentContext(mr_iid=1, comment_type=CommentType.NOTE)
    dialog = CommentDialog(context, MagicMock(), "vi")

    source = inspect.getsource(dialog.compose)
    assert "dialog-container" in source
    assert "Vertical" in source


@pytest.mark.asyncio
async def test_content_panel_has_sbs_datatable_widgets():
    """ContentPanel が #diff-table-left と #diff-table-right DataTable を持つことを確認する。"""
    from textual.app import App, ComposeResult
    from textual.widgets import DataTable

    from glreview.tui.widgets.content_panel import ContentPanel

    class _TestApp(App):
        def compose(self) -> ComposeResult:
            yield ContentPanel(MagicMock(), MagicMock())

    test_app = _TestApp()
    async with test_app.run_test() as _:
        left = test_app.query_one("#diff-table-left", DataTable)
        right = test_app.query_one("#diff-table-right", DataTable)
        assert left is not None
        assert right is not None


def test_content_panel_has_required_bindings():
    """ContentPanel が t/w/c バインディングを持つことを確認する。"""
    from glreview.tui.widgets.content_panel import ContentPanel

    keys = {b.key for b in ContentPanel.BINDINGS}
    assert "w" in keys
    assert "t" in keys
    assert "c" in keys


@pytest.mark.asyncio
async def test_clear_content_hides_unified_container():
    """clear_content() 後に #unified-container が非表示になることを確認する。

    バグ再現: clear_content() が #diff-table.display = False にするだけで
    #unified-container を隠さないため、次回の diff 表示時に差分領域が空白になる。
    """
    from textual.app import App, ComposeResult

    from glreview.tui.entities import DiffViewMode
    from glreview.tui.widgets.content_panel import ContentPanel

    class _TestApp(App):
        def compose(self) -> ComposeResult:
            yield ContentPanel(MagicMock(), MagicMock())

    test_app = _TestApp()
    async with test_app.run_test() as pilot:
        panel = test_app.query_one(ContentPanel)
        panel._diff_mode = DiffViewMode.UNIFIED
        # unified モードで diff 表示領域を表示する
        panel._show_diff_table()
        await pilot.pause()
        unified_container = test_app.query_one("#unified-container")
        assert unified_container.display is True
        # clear_content() でリセット
        await panel.clear_content()
        await pilot.pause()
        # unified-container も非表示になっていること
        assert unified_container.display is False


@pytest.mark.asyncio
async def test_diff_table_visible_after_clear_and_reload():
    """clear_content() → _show_diff_table() で #diff-table が表示されることを確認する。

    バグ再現シナリオ:
    1. unified モードで diff 表示 → #diff-table.display=True
    2. MR 切り替えで clear_content() → #unified-container が非表示になる
    3. 別ファイルの diff 表示 → #unified-container と #diff-table が両方表示される
    """
    from textual.app import App, ComposeResult
    from textual.widgets import DataTable

    from glreview.tui.entities import DiffViewMode
    from glreview.tui.widgets.content_panel import ContentPanel

    class _TestApp(App):
        def compose(self) -> ComposeResult:
            yield ContentPanel(MagicMock(), MagicMock())

    test_app = _TestApp()
    async with test_app.run_test() as pilot:
        panel = test_app.query_one(ContentPanel)
        panel._diff_mode = DiffViewMode.UNIFIED
        # 1回目の diff 表示
        panel._show_diff_table()
        await pilot.pause()
        # clear_content() でリセット（MR 切り替えに相当）
        await panel.clear_content()
        await pilot.pause()
        # 2回目の diff 表示（別ファイル選択に相当）
        panel._show_diff_table()
        await pilot.pause()
        # #diff-table が表示されていること（修正前はここで False になる）
        table = test_app.query_one("#diff-table", DataTable)
        assert table.display is True
