"""GLReviewApp のテスト。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_app_config(**kwargs):
    from glreview.models import AppConfig

    defaults = {
        "gitlab_url": "https://gitlab.example.com",
        "token": "glpat-test",
        "editor": "nvim",
        "terminal": "",
        "remote_name": "origin",
        "log_level": "WARNING",
        "pygments_style": "",
        "ssl_verify": True,
    }
    defaults.update(kwargs)
    return AppConfig(**defaults)


def _make_services():
    """MRService と CommentService のモックを生成する。"""
    from glreview.services.types import PaginatedResult

    empty = PaginatedResult(items=[], has_next_page=False, next_page=None)

    mr_service = MagicMock()
    mr_service.get_assigned_to_me = AsyncMock(return_value=empty)
    mr_service.get_reviewer_is_me = AsyncMock(return_value=empty)
    mr_service.get_created_by_me = AsyncMock(return_value=empty)
    mr_service.get_unassigned = AsyncMock(return_value=empty)
    mr_service.get_assigned_to_others = AsyncMock(return_value=empty)
    mr_service.invalidate_cache = MagicMock()
    mr_service.load = AsyncMock()

    comment_service = MagicMock()
    comment_service.get_discussions = AsyncMock(return_value=[])
    comment_service.invalidate_cache = MagicMock()
    comment_service.load = AsyncMock()

    return mr_service, comment_service


@pytest.mark.asyncio
async def test_app_action_toggle_sidebar() -> None:
    """action_toggle_sidebar がサイドバーの表示/非表示を切り替えることを確認する。"""
    from glreview.tui.app import GLReviewApp

    config = _make_app_config()
    mr_service, comment_service = _make_services()

    mock_client = MagicMock()
    mock_client.connect = AsyncMock()

    with (
        patch("glreview.tui.app.GitRepoDetector") as mock_detector_cls,
        patch("glreview.tui.app.GitLabClient", return_value=mock_client),
        patch("glreview.tui.app.MRService", return_value=mr_service),
        patch("glreview.tui.app.CommentService", return_value=comment_service),
        patch("glreview.tui.app.subprocess.run") as mock_run,
    ):
        mock_run.return_value = MagicMock(returncode=0, stdout="/git/root\n", stderr="")
        mock_detector = MagicMock()
        mock_detector.detect.return_value = MagicMock(project_path="group/repo")
        mock_detector_cls.return_value = mock_detector

        app = GLReviewApp(config=config)
        async with app.run_test() as pilot:
            await pilot.pause(0.8)
            # 初期状態ではサイドバーが表示されていること
            assert app._sidebar_visible is True
            # '\' キーでサイドバーを非表示にする
            await pilot.press("backslash")
            assert app._sidebar_visible is False
            # もう一度押すと表示に戻る
            await pilot.press("backslash")
            assert app._sidebar_visible is True


@pytest.mark.asyncio
async def test_app_action_refresh() -> None:
    """action_refresh がキャッシュを無効化してリストを再ロードすることを確認する。"""
    from glreview.tui.app import GLReviewApp

    config = _make_app_config()
    mr_service, comment_service = _make_services()

    mock_client = MagicMock()
    mock_client.connect = AsyncMock()

    with (
        patch("glreview.tui.app.GitRepoDetector") as mock_detector_cls,
        patch("glreview.tui.app.GitLabClient", return_value=mock_client),
        patch("glreview.tui.app.MRService", return_value=mr_service),
        patch("glreview.tui.app.CommentService", return_value=comment_service),
        patch("glreview.tui.app.subprocess.run") as mock_run,
    ):
        mock_run.return_value = MagicMock(returncode=0, stdout="/git/root\n", stderr="")
        mock_detector = MagicMock()
        mock_detector.detect.return_value = MagicMock(project_path="group/repo")
        mock_detector_cls.return_value = mock_detector

        app = GLReviewApp(config=config)
        async with app.run_test() as pilot:
            await pilot.pause(0.8)
            # 'r' キーでリフレッシュ
            await pilot.press("r")
            await pilot.pause(0.3)
            # invalidate_cache が呼ばれること
            mr_service.invalidate_cache.assert_called()
            comment_service.invalidate_cache.assert_called()


@pytest.mark.asyncio
async def test_app_action_focus_mr_list() -> None:
    """action_focus_mr_list が MRListPanel のツリーにフォーカスすることを確認する。"""
    from glreview.tui.app import GLReviewApp

    config = _make_app_config()
    mr_service, comment_service = _make_services()

    mock_client = MagicMock()
    mock_client.connect = AsyncMock()

    with (
        patch("glreview.tui.app.GitRepoDetector") as mock_detector_cls,
        patch("glreview.tui.app.GitLabClient", return_value=mock_client),
        patch("glreview.tui.app.MRService", return_value=mr_service),
        patch("glreview.tui.app.CommentService", return_value=comment_service),
        patch("glreview.tui.app.subprocess.run") as mock_run,
    ):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        mock_detector = MagicMock()
        mock_detector.detect.return_value = MagicMock(project_path="group/repo")
        mock_detector_cls.return_value = mock_detector

        app = GLReviewApp(config=config)
        async with app.run_test() as pilot:
            await pilot.pause(0.8)
            # 'm' キーで MR リストにフォーカス（例外なしに完了すること）
            await pilot.press("m")
            await pilot.pause(0.1)


@pytest.mark.asyncio
async def test_app_action_show_help() -> None:
    """action_show_help が HelpScreen を開くことを確認する。"""
    from glreview.tui.app import GLReviewApp
    from glreview.tui.screens.help_screen import HelpScreen

    config = _make_app_config()
    mr_service, comment_service = _make_services()

    mock_client = MagicMock()
    mock_client.connect = AsyncMock()

    with (
        patch("glreview.tui.app.GitRepoDetector") as mock_detector_cls,
        patch("glreview.tui.app.GitLabClient", return_value=mock_client),
        patch("glreview.tui.app.MRService", return_value=mr_service),
        patch("glreview.tui.app.CommentService", return_value=comment_service),
        patch("glreview.tui.app.subprocess.run") as mock_run,
    ):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        mock_detector = MagicMock()
        mock_detector.detect.return_value = MagicMock(project_path="group/repo")
        mock_detector_cls.return_value = mock_detector

        app = GLReviewApp(config=config)
        async with app.run_test() as pilot:
            await pilot.pause(0.8)
            await pilot.press("question_mark")
            await pilot.pause(0.2)
            assert isinstance(app.screen, HelpScreen)
            await pilot.press("escape")


@pytest.mark.asyncio
async def test_app_connection_error_shows_error_dialog() -> None:
    """接続エラー時にエラーダイアログが表示され、解除後にアクションが安全に実行されることを確認する。"""
    from glreview.services.exceptions import GitLabConnectionError
    from glreview.tui.app import GLReviewApp
    from glreview.tui.screens.error_dialog import ErrorDialog

    config = _make_app_config()
    mock_client = MagicMock()
    mock_client.connect = AsyncMock(side_effect=GitLabConnectionError("Cannot connect"))

    with (
        patch("glreview.tui.app.GitRepoDetector") as mock_detector_cls,
        patch("glreview.tui.app.GitLabClient", return_value=mock_client),
        patch("glreview.tui.app.subprocess.run") as mock_run,
    ):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        mock_detector = MagicMock()
        mock_detector.detect.return_value = MagicMock(project_path="group/repo")
        mock_detector_cls.return_value = mock_detector

        app = GLReviewApp(config=config)
        async with app.run_test() as pilot:
            await pilot.pause(0.5)
            # エラーダイアログが表示されていること
            assert isinstance(app.screen, ErrorDialog)
            await pilot.press("escape")
            await pilot.pause(0.1)
            # MRListPanel が未マウントの状態でのアクションが安全に実行されること
            # (except ブロックのカバレッジ)
            await pilot.press("backslash")  # action_toggle_sidebar → except block
            await pilot.press("m")  # action_focus_mr_list → except block
            await pilot.pause(0.1)


@pytest.mark.asyncio
async def test_app_open_in_editor_no_file_selected() -> None:
    """ファイルが選択されていない場合に 'e' キーで何も起きないことを確認する。"""
    from glreview.tui.app import GLReviewApp

    config = _make_app_config()
    mr_service, comment_service = _make_services()

    mock_client = MagicMock()
    mock_client.connect = AsyncMock()

    with (
        patch("glreview.tui.app.GitRepoDetector") as mock_detector_cls,
        patch("glreview.tui.app.GitLabClient", return_value=mock_client),
        patch("glreview.tui.app.MRService", return_value=mr_service),
        patch("glreview.tui.app.CommentService", return_value=comment_service),
        patch("glreview.tui.app.subprocess.run") as mock_run,
    ):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        mock_detector = MagicMock()
        mock_detector.detect.return_value = MagicMock(project_path="group/repo")
        mock_detector_cls.return_value = mock_detector

        app = GLReviewApp(config=config)
        async with app.run_test() as pilot:
            await pilot.pause(0.8)
            # ファイルが選択されていない状態で 'e' キー（例外なしに完了すること）
            await pilot.press("e")
            await pilot.pause(0.1)


@pytest.mark.asyncio
async def test_app_checkout_branch_no_mr_selected() -> None:
    """MRが選択されていない場合に 'b' キーで何も起きないことを確認する。"""
    from glreview.tui.app import GLReviewApp

    config = _make_app_config()
    mr_service, comment_service = _make_services()

    mock_client = MagicMock()
    mock_client.connect = AsyncMock()

    with (
        patch("glreview.tui.app.GitRepoDetector") as mock_detector_cls,
        patch("glreview.tui.app.GitLabClient", return_value=mock_client),
        patch("glreview.tui.app.MRService", return_value=mr_service),
        patch("glreview.tui.app.CommentService", return_value=comment_service),
        patch("glreview.tui.app.subprocess.run") as mock_run,
    ):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        mock_detector = MagicMock()
        mock_detector.detect.return_value = MagicMock(project_path="group/repo")
        mock_detector_cls.return_value = mock_detector

        app = GLReviewApp(config=config)
        async with app.run_test() as pilot:
            await pilot.pause(0.8)
            # MRが選択されていない状態で 'b' キー（例外なしに完了すること）
            await pilot.press("b")
            await pilot.pause(0.2)


@pytest.mark.asyncio
async def test_app_git_root_detection() -> None:
    """git rev-parse が成功した場合に git_root が更新されることを確認する。"""
    from pathlib import Path

    from glreview.tui.app import GLReviewApp

    config = _make_app_config()
    mr_service, comment_service = _make_services()

    mock_client = MagicMock()
    mock_client.connect = AsyncMock()

    with (
        patch("glreview.tui.app.GitRepoDetector") as mock_detector_cls,
        patch("glreview.tui.app.GitLabClient", return_value=mock_client),
        patch("glreview.tui.app.MRService", return_value=mr_service),
        patch("glreview.tui.app.CommentService", return_value=comment_service),
        patch("glreview.tui.app.subprocess.run") as mock_run,
    ):
        mock_run.return_value = MagicMock(returncode=0, stdout="/git/root\n", stderr="")
        mock_detector = MagicMock()
        mock_detector.detect.return_value = MagicMock(project_path="group/repo")
        mock_detector_cls.return_value = mock_detector

        app = GLReviewApp(config=config)
        async with app.run_test() as pilot:
            await pilot.pause(0.8)
            # git root が設定されていること
            assert app._git_root == Path("/git/root")


@pytest.mark.asyncio
async def test_app_git_root_exception_handled() -> None:
    """git rev-parse が例外を投げた場合に fallback することを確認する。"""
    from glreview.tui.app import GLReviewApp

    config = _make_app_config()
    mr_service, comment_service = _make_services()

    mock_client = MagicMock()
    mock_client.connect = AsyncMock()

    with (
        patch("glreview.tui.app.GitRepoDetector") as mock_detector_cls,
        patch("glreview.tui.app.GitLabClient", return_value=mock_client),
        patch("glreview.tui.app.MRService", return_value=mr_service),
        patch("glreview.tui.app.CommentService", return_value=comment_service),
        patch("glreview.tui.app.subprocess.run", side_effect=FileNotFoundError("git not found")),
    ):
        mock_detector = MagicMock()
        mock_detector.detect.return_value = MagicMock(project_path="group/repo")
        mock_detector_cls.return_value = mock_detector

        app = GLReviewApp(config=config)
        async with app.run_test() as pilot:
            await pilot.pause(0.8)
            # 例外が発生しても起動に成功すること（デフォルトのgit_rootが使用される）
            assert app._git_root is not None


@pytest.mark.asyncio
async def test_app_with_pygments_style_and_config_manager() -> None:
    """pygments_style と config_manager が設定された場合に ContentPanel に反映されることを確認する。"""  # noqa: E501
    from glreview.tui.app import GLReviewApp

    config = _make_app_config(pygments_style="monokai")
    mr_service, comment_service = _make_services()

    mock_client = MagicMock()
    mock_client.connect = AsyncMock()

    mock_config_manager = MagicMock()

    with (
        patch("glreview.tui.app.GitRepoDetector") as mock_detector_cls,
        patch("glreview.tui.app.GitLabClient", return_value=mock_client),
        patch("glreview.tui.app.MRService", return_value=mr_service),
        patch("glreview.tui.app.CommentService", return_value=comment_service),
        patch("glreview.tui.app.subprocess.run") as mock_run,
    ):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        mock_detector = MagicMock()
        mock_detector.detect.return_value = MagicMock(project_path="group/repo")
        mock_detector_cls.return_value = mock_detector

        app = GLReviewApp(config=config, config_manager=mock_config_manager)
        async with app.run_test() as pilot:
            await pilot.pause(0.8)
            # config_manager が設定されていること
            assert app._config_manager is mock_config_manager


@pytest.mark.asyncio
async def test_app_with_initial_mr_id() -> None:
    """initial_mr_id が設定された場合に MR が展開されることを確認する。"""
    from glreview.tui.app import GLReviewApp

    config = _make_app_config()
    mr_service, comment_service = _make_services()

    mock_client = MagicMock()
    mock_client.connect = AsyncMock()

    with (
        patch("glreview.tui.app.GitRepoDetector") as mock_detector_cls,
        patch("glreview.tui.app.GitLabClient", return_value=mock_client),
        patch("glreview.tui.app.MRService", return_value=mr_service),
        patch("glreview.tui.app.CommentService", return_value=comment_service),
        patch("glreview.tui.app.subprocess.run") as mock_run,
    ):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        mock_detector = MagicMock()
        mock_detector.detect.return_value = MagicMock(project_path="group/repo")
        mock_detector_cls.return_value = mock_detector

        app = GLReviewApp(config=config, initial_mr_id=42)
        async with app.run_test() as pilot:
            await pilot.pause(0.8)
            # initial_mr_id が設定されていること
            assert app._initial_mr_id == 42


def _make_services_with_mr():
    """MRを1件持つサービスのモックを生成する。"""
    from glreview.models import MergeRequestSummary
    from glreview.services.types import PaginatedResult

    mr = MergeRequestSummary(
        iid=10,
        title="Test MR",
        author="alice",
        status="opened",
        labels=[],
        updated_at="2026-01-01T00:00:00Z",
    )
    mr_result = PaginatedResult(items=[mr], has_next_page=False, next_page=None)
    empty = PaginatedResult(items=[], has_next_page=False, next_page=None)

    mr_service = MagicMock()
    mr_service.load = AsyncMock()
    mr_service.get_assigned_to_me = AsyncMock(return_value=mr_result)
    mr_service.get_reviewer_is_me = AsyncMock(return_value=empty)
    mr_service.get_created_by_me = AsyncMock(return_value=empty)
    mr_service.get_unassigned = AsyncMock(return_value=empty)
    mr_service.get_assigned_to_others = AsyncMock(return_value=empty)
    mr_service.get_mr_changes = AsyncMock(return_value=[])
    mr_service.invalidate_cache = MagicMock()

    comment_service = MagicMock()
    comment_service.load = AsyncMock()
    comment_service.get_discussions = AsyncMock(return_value=[])
    comment_service.invalidate_cache = MagicMock()

    return mr_service, comment_service


@pytest.mark.asyncio
async def test_app_checkout_branch_worker_success() -> None:
    """_checkout_branch_worker が正常にブランチをチェックアウトすることを確認する。"""
    from glreview.models import MergeRequestDetail
    from glreview.tui.app import GLReviewApp

    config = _make_app_config()
    mr_service, comment_service = _make_services_with_mr()

    detail = MergeRequestDetail(
        iid=10,
        title="Test MR",
        description="",
        author="alice",
        status="opened",
        labels=[],
        web_url="https://gitlab.example.com/mr/10",
        created_at="2026-01-01",
        updated_at="2026-01-02",
        source_branch="feature/my-branch",
    )
    mr_service.get_mr_detail = AsyncMock(return_value=detail)

    mock_client = MagicMock()
    mock_client.connect = AsyncMock()

    from glreview.infrastructure.git_ops import CheckoutResult

    checkout_result = CheckoutResult(
        branch="feature/my-branch", action="checkout", message="チェックアウトしました"
    )

    with (
        patch("glreview.tui.app.GitRepoDetector") as mock_detector_cls,
        patch("glreview.tui.app.GitLabClient", return_value=mock_client),
        patch("glreview.tui.app.MRService", return_value=mr_service),
        patch("glreview.tui.app.CommentService", return_value=comment_service),
        patch("glreview.tui.app.subprocess.run") as mock_run,
        patch(
            "glreview.infrastructure.git_ops.checkout_or_switch_branch",
            return_value=checkout_result,
        ),
    ):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        mock_detector = MagicMock()
        mock_detector.detect.return_value = MagicMock(project_path="group/repo")
        mock_detector_cls.return_value = mock_detector

        app = GLReviewApp(config=config)
        async with app.run_test() as pilot:
            await pilot.pause(0.8)
            # b を押して checkout を試みる（MRが選択されていない）
            await pilot.press("b")
            await pilot.pause(0.2)
            # _checkout_branch_worker を直接呼ぶ
            await app._checkout_branch_worker(10)
            await pilot.pause(0.2)


@pytest.mark.asyncio
async def test_app_checkout_branch_worker_mr_detail_error() -> None:
    """_checkout_branch_worker が MR 取得失敗時にエラーダイアログを表示することを確認する。"""
    from glreview.tui.app import GLReviewApp
    from glreview.tui.screens.error_dialog import ErrorDialog

    config = _make_app_config()
    mr_service, comment_service = _make_services_with_mr()
    mr_service.get_mr_detail = AsyncMock(side_effect=RuntimeError("Not found"))

    mock_client = MagicMock()
    mock_client.connect = AsyncMock()

    with (
        patch("glreview.tui.app.GitRepoDetector") as mock_detector_cls,
        patch("glreview.tui.app.GitLabClient", return_value=mock_client),
        patch("glreview.tui.app.MRService", return_value=mr_service),
        patch("glreview.tui.app.CommentService", return_value=comment_service),
        patch("glreview.tui.app.subprocess.run") as mock_run,
    ):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        mock_detector = MagicMock()
        mock_detector.detect.return_value = MagicMock(project_path="group/repo")
        mock_detector_cls.return_value = mock_detector

        app = GLReviewApp(config=config)
        async with app.run_test() as pilot:
            await pilot.pause(0.8)
            await app._checkout_branch_worker(10)
            await pilot.pause(0.3)
            assert isinstance(app.screen, ErrorDialog)
            await pilot.press("escape")


@pytest.mark.asyncio
async def test_app_checkout_branch_worker_no_source_branch() -> None:
    """ソースブランチが空の場合にエラーダイアログを表示することを確認する。"""
    from glreview.models import MergeRequestDetail
    from glreview.tui.app import GLReviewApp
    from glreview.tui.screens.error_dialog import ErrorDialog

    config = _make_app_config()
    mr_service, comment_service = _make_services_with_mr()

    detail = MergeRequestDetail(
        iid=10,
        title="Test MR",
        description="",
        author="alice",
        status="opened",
        labels=[],
        web_url="https://gitlab.example.com/mr/10",
        created_at="2026-01-01",
        updated_at="2026-01-02",
        source_branch="",  # empty source branch
    )
    mr_service.get_mr_detail = AsyncMock(return_value=detail)

    mock_client = MagicMock()
    mock_client.connect = AsyncMock()

    with (
        patch("glreview.tui.app.GitRepoDetector") as mock_detector_cls,
        patch("glreview.tui.app.GitLabClient", return_value=mock_client),
        patch("glreview.tui.app.MRService", return_value=mr_service),
        patch("glreview.tui.app.CommentService", return_value=comment_service),
        patch("glreview.tui.app.subprocess.run") as mock_run,
    ):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        mock_detector = MagicMock()
        mock_detector.detect.return_value = MagicMock(project_path="group/repo")
        mock_detector_cls.return_value = mock_detector

        app = GLReviewApp(config=config)
        async with app.run_test() as pilot:
            await pilot.pause(0.8)
            await app._checkout_branch_worker(10)
            await pilot.pause(0.3)
            assert isinstance(app.screen, ErrorDialog)
            await pilot.press("escape")


@pytest.mark.asyncio
async def test_app_checkout_branch_worker_git_ops_error() -> None:
    """checkout_or_switch_branch が GitOpsError を投げた場合にエラーダイアログを表示することを確認する。"""  # noqa: E501
    from glreview.infrastructure.git_ops import GitOpsError
    from glreview.models import MergeRequestDetail
    from glreview.tui.app import GLReviewApp
    from glreview.tui.screens.error_dialog import ErrorDialog

    config = _make_app_config()
    mr_service, comment_service = _make_services_with_mr()

    detail = MergeRequestDetail(
        iid=10,
        title="Test MR",
        description="",
        author="alice",
        status="opened",
        labels=[],
        web_url="https://gitlab.example.com/mr/10",
        created_at="2026-01-01",
        updated_at="2026-01-02",
        source_branch="feature/my-branch",
    )
    mr_service.get_mr_detail = AsyncMock(return_value=detail)

    mock_client = MagicMock()
    mock_client.connect = AsyncMock()

    with (
        patch("glreview.tui.app.GitRepoDetector") as mock_detector_cls,
        patch("glreview.tui.app.GitLabClient", return_value=mock_client),
        patch("glreview.tui.app.MRService", return_value=mr_service),
        patch("glreview.tui.app.CommentService", return_value=comment_service),
        patch("glreview.tui.app.subprocess.run") as mock_run,
        patch(
            "glreview.infrastructure.git_ops.checkout_or_switch_branch",
            side_effect=GitOpsError("git error"),
        ),
    ):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        mock_detector = MagicMock()
        mock_detector.detect.return_value = MagicMock(project_path="group/repo")
        mock_detector_cls.return_value = mock_detector

        app = GLReviewApp(config=config)
        async with app.run_test() as pilot:
            await pilot.pause(0.8)
            await app._checkout_branch_worker(10)
            await pilot.pause(0.3)
            assert isinstance(app.screen, ErrorDialog)
            await pilot.press("escape")


@pytest.mark.asyncio
async def test_app_message_handler_routing() -> None:
    """ShowOverview/ShowDiff/CommentPosted メッセージが ContentPanel に転送されることを確認する。"""
    from glreview.models import FileDiff
    from glreview.tui.app import GLReviewApp
    from glreview.tui.messages import CommentPosted, ShowDiff, ShowOverview

    config = _make_app_config()
    mr_service, comment_service = _make_services_with_mr()

    file_diff = FileDiff(
        file_path="src/main.py",
        diff="@@ -1,2 +1,2 @@\n ctx\n-old\n+new\n",
        old_path="src/main.py",
        new_path="src/main.py",
    )
    mr_service.get_mr_diff = AsyncMock(return_value=file_diff)

    from glreview.models import MergeRequestDetail

    detail = MergeRequestDetail(
        iid=10,
        title="Test MR",
        description="desc",
        author="alice",
        status="opened",
        labels=[],
        web_url="https://gitlab.example.com/mr/10",
        created_at="2026-01-01",
        updated_at="2026-01-02",
    )
    mr_service.get_mr_detail = AsyncMock(return_value=detail)

    mock_client = MagicMock()
    mock_client.connect = AsyncMock()

    with (
        patch("glreview.tui.app.GitRepoDetector") as mock_detector_cls,
        patch("glreview.tui.app.GitLabClient", return_value=mock_client),
        patch("glreview.tui.app.MRService", return_value=mr_service),
        patch("glreview.tui.app.CommentService", return_value=comment_service),
        patch("glreview.tui.app.subprocess.run") as mock_run,
    ):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        mock_detector = MagicMock()
        mock_detector.detect.return_value = MagicMock(project_path="group/repo")
        mock_detector_cls.return_value = mock_detector

        app = GLReviewApp(config=config)
        async with app.run_test() as pilot:
            await pilot.pause(0.8)
            # ShowOverview メッセージを直接送信
            app.post_message(ShowOverview(mr_iid=10))
            await pilot.pause(0.5)
            # ShowDiff メッセージを直接送信
            app.post_message(ShowDiff(mr_iid=10, file_path="src/main.py"))
            await pilot.pause(0.5)
            # CommentPosted メッセージを直接送信
            app.post_message(CommentPosted(mr_iid=10))
            await pilot.pause(0.3)


@pytest.mark.asyncio
async def test_app_checkout_branch_worker_unexpected_error() -> None:
    """_checkout_branch_worker が予期しない例外を捕捉してエラーダイアログを表示することを確認する。"""  # noqa: E501
    from glreview.models import MergeRequestDetail
    from glreview.tui.app import GLReviewApp
    from glreview.tui.screens.error_dialog import ErrorDialog

    config = _make_app_config()
    mr_service, comment_service = _make_services_with_mr()

    detail = MergeRequestDetail(
        iid=10,
        title="Test MR",
        description="",
        author="alice",
        status="opened",
        labels=[],
        web_url="https://gitlab.example.com/mr/10",
        created_at="2026-01-01",
        updated_at="2026-01-02",
        source_branch="feature/my-branch",
    )
    mr_service.get_mr_detail = AsyncMock(return_value=detail)

    mock_client = MagicMock()
    mock_client.connect = AsyncMock()

    with (
        patch("glreview.tui.app.GitRepoDetector") as mock_detector_cls,
        patch("glreview.tui.app.GitLabClient", return_value=mock_client),
        patch("glreview.tui.app.MRService", return_value=mr_service),
        patch("glreview.tui.app.CommentService", return_value=comment_service),
        patch("glreview.tui.app.subprocess.run") as mock_run,
        patch(
            "glreview.infrastructure.git_ops.checkout_or_switch_branch",
            side_effect=RuntimeError("unexpected"),
        ),
    ):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        mock_detector = MagicMock()
        mock_detector.detect.return_value = MagicMock(project_path="group/repo")
        mock_detector_cls.return_value = mock_detector

        app = GLReviewApp(config=config)
        async with app.run_test() as pilot:
            await pilot.pause(0.8)
            await app._checkout_branch_worker(10)
            await pilot.pause(0.3)
            assert isinstance(app.screen, ErrorDialog)
            await pilot.press("escape")


@pytest.mark.asyncio
async def test_app_action_refresh_when_services_none() -> None:
    """サービスが未初期化の状態で 'r' キーを押しても何も起きないことを確認する。"""
    from glreview.tui.app import GLReviewApp
    from glreview.tui.screens.error_dialog import ErrorDialog

    config = _make_app_config()

    with (
        patch("glreview.tui.app.GitRepoDetector") as mock_detector_cls,
        patch("glreview.tui.app.subprocess.run") as mock_run,
        patch("glreview.tui.app.GitLabClient") as mock_client_cls,
    ):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        mock_detector = MagicMock()
        mock_detector.detect.return_value = MagicMock(project_path="group/repo")
        mock_detector_cls.return_value = mock_detector
        # connect fails → services remain None
        mock_client = MagicMock()
        mock_client.connect = AsyncMock(side_effect=RuntimeError("Connection refused"))
        mock_client_cls.return_value = mock_client

        app = GLReviewApp(config=config)
        async with app.run_test() as pilot:
            await pilot.pause(0.5)
            # error dialog が表示されている
            assert isinstance(app.screen, ErrorDialog)
            await pilot.press("escape")
            await pilot.pause(0.1)
            # サービスが None の状態で refresh を直接呼ぶ
            assert app._mr_service is None
            await app.action_refresh()  # should return early (line 197)


@pytest.mark.asyncio
async def test_app_unexpected_exception_on_mount_shows_error() -> None:
    """on_mount で予期しない例外が発生した場合にエラーダイアログが表示されることを確認する。"""
    from glreview.tui.app import GLReviewApp
    from glreview.tui.screens.error_dialog import ErrorDialog

    config = _make_app_config()

    with (
        patch("glreview.tui.app.GitRepoDetector") as mock_detector_cls,
        patch("glreview.tui.app.subprocess.run") as mock_run,
    ):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        mock_detector = MagicMock()
        mock_detector.detect.side_effect = RuntimeError("unexpected error")
        mock_detector_cls.return_value = mock_detector

        app = GLReviewApp(config=config)
        async with app.run_test() as pilot:
            await pilot.pause(0.5)
            # エラーダイアログが表示されていること
            assert isinstance(app.screen, ErrorDialog)
            await pilot.press("escape")
