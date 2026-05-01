"""CommentDialog のテスト。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from glreview.models import CommentContext, CommentType


def _make_inline_context(mr_iid: int = 1) -> CommentContext:
    return CommentContext(
        mr_iid=mr_iid,
        comment_type=CommentType.INLINE,
        file_path="src/main.py",
        line=10,
        line_type="new",
    )


def _make_note_context(mr_iid: int = 1) -> CommentContext:
    return CommentContext(
        mr_iid=mr_iid,
        comment_type=CommentType.NOTE,
    )


def _make_reply_context(mr_iid: int = 1, discussion_id: str = "d1") -> CommentContext:
    return CommentContext(
        mr_iid=mr_iid,
        comment_type=CommentType.REPLY,
        discussion_id=discussion_id,
    )


class TestBuildHeader:
    def test_inline_header(self) -> None:
        from glreview.tui.screens.comment_dialog import CommentDialog

        ctx = _make_inline_context()
        dialog = CommentDialog(ctx, MagicMock(), "nvim")
        title, subtitle = dialog._build_header()
        assert "Inline" in title
        assert "src/main.py" in subtitle
        assert "10" in subtitle

    def test_note_header(self) -> None:
        from glreview.tui.screens.comment_dialog import CommentDialog

        ctx = _make_note_context()
        dialog = CommentDialog(ctx, MagicMock(), "nvim")
        title, subtitle = dialog._build_header()
        assert "Note" in title
        assert "MR" in subtitle

    def test_reply_header(self) -> None:
        from glreview.tui.screens.comment_dialog import CommentDialog

        ctx = _make_reply_context()
        dialog = CommentDialog(ctx, MagicMock(), "nvim")
        title, subtitle = dialog._build_header()
        assert "Reply" in title
        assert subtitle == ""


@pytest.mark.asyncio
async def test_comment_dialog_renders_and_cancel() -> None:
    """CommentDialog がレンダリングされて Escape でキャンセルされることを確認する。"""
    from textual.app import App, ComposeResult
    from textual.widgets import Label

    from glreview.tui.screens.comment_dialog import CommentDialog

    ctx = _make_inline_context()
    comment_service = MagicMock()

    class _TestApp(App):
        def compose(self) -> ComposeResult:
            yield Label("base")

        async def on_mount(self) -> None:
            await self.push_screen(CommentDialog(ctx, comment_service, "nvim"))

    test_app = _TestApp()
    async with test_app.run_test() as pilot:
        assert isinstance(test_app.screen, CommentDialog)
        await pilot.press("escape")
        assert not isinstance(test_app.screen, CommentDialog)


@pytest.mark.asyncio
async def test_comment_dialog_submit_empty_shows_error() -> None:
    """空のテキストで Submit するとエラーが表示されることを確認する。"""
    from textual.app import App, ComposeResult
    from textual.widgets import Label

    from glreview.tui.screens.comment_dialog import CommentDialog

    ctx = _make_inline_context()
    comment_service = MagicMock()

    class _TestApp(App):
        def compose(self) -> ComposeResult:
            yield Label("base")

        async def on_mount(self) -> None:
            await self.push_screen(CommentDialog(ctx, comment_service, "nvim"))

    test_app = _TestApp()
    async with test_app.run_test() as pilot:
        assert isinstance(test_app.screen, CommentDialog)
        # Ctrl+S で Submit（テキストが空なのでエラーになるはず）
        await pilot.press("ctrl+s")
        await pilot.pause(0.1)
        # ダイアログは閉じていない
        assert isinstance(test_app.screen, CommentDialog)


@pytest.mark.asyncio
async def test_comment_dialog_cancel_button() -> None:
    """Cancel ボタンでダイアログが閉じることを確認する。"""
    from textual.app import App, ComposeResult
    from textual.widgets import Label

    from glreview.tui.screens.comment_dialog import CommentDialog

    ctx = _make_note_context()
    comment_service = MagicMock()

    class _TestApp(App):
        def compose(self) -> ComposeResult:
            yield Label("base")

        async def on_mount(self) -> None:
            await self.push_screen(CommentDialog(ctx, comment_service, "nvim"))

    test_app = _TestApp()
    async with test_app.run_test() as pilot:
        assert isinstance(test_app.screen, CommentDialog)
        await pilot.click("#cancel-button")
        await pilot.pause(0.1)
        assert not isinstance(test_app.screen, CommentDialog)


@pytest.mark.asyncio
async def test_comment_dialog_submit_note_success() -> None:
    """NOTE タイプのコメントが正常に投稿されることを確認する。"""
    from textual.app import App, ComposeResult
    from textual.widgets import Label, TextArea

    from glreview.tui.screens.comment_dialog import CommentDialog

    ctx = _make_note_context()
    comment_service = MagicMock()
    comment_service.add_note = AsyncMock(return_value=None)

    class _TestApp(App):
        def compose(self) -> ComposeResult:
            yield Label("base")

        async def on_mount(self) -> None:
            await self.push_screen(CommentDialog(ctx, comment_service, "nvim"))

    test_app = _TestApp()
    async with test_app.run_test() as pilot:
        assert isinstance(test_app.screen, CommentDialog)
        # テキストエリアにテキストを入力
        text_area = test_app.screen.query_one(TextArea)
        text_area.insert("Hello world comment")
        await pilot.press("ctrl+s")
        await pilot.pause(0.3)
        # submit されてダイアログが閉じる
        assert not isinstance(test_app.screen, CommentDialog)
        comment_service.add_note.assert_called_once_with(mr_iid=1, body="Hello world comment")


@pytest.mark.asyncio
async def test_comment_dialog_submit_inline_success() -> None:
    """INLINE タイプのコメントが正常に投稿されることを確認する。"""
    from textual.app import App, ComposeResult
    from textual.widgets import Label, TextArea

    from glreview.tui.screens.comment_dialog import CommentDialog

    ctx = _make_inline_context()
    comment_service = MagicMock()
    comment_service.add_inline_comment = AsyncMock(return_value=None)

    class _TestApp(App):
        def compose(self) -> ComposeResult:
            yield Label("base")

        async def on_mount(self) -> None:
            await self.push_screen(CommentDialog(ctx, comment_service, "nvim"))

    test_app = _TestApp()
    async with test_app.run_test() as pilot:
        assert isinstance(test_app.screen, CommentDialog)
        text_area = test_app.screen.query_one(TextArea)
        text_area.insert("Inline comment text")
        await pilot.press("ctrl+s")
        await pilot.pause(0.3)
        assert not isinstance(test_app.screen, CommentDialog)
        comment_service.add_inline_comment.assert_called_once()


@pytest.mark.asyncio
async def test_comment_dialog_submit_reply_success() -> None:
    """REPLY タイプのコメントが正常に投稿されることを確認する。"""
    from textual.app import App, ComposeResult
    from textual.widgets import Label, TextArea

    from glreview.tui.screens.comment_dialog import CommentDialog

    ctx = _make_reply_context(discussion_id="disc123")
    comment_service = MagicMock()
    comment_service.reply_to_discussion = AsyncMock(return_value=None)

    class _TestApp(App):
        def compose(self) -> ComposeResult:
            yield Label("base")

        async def on_mount(self) -> None:
            await self.push_screen(CommentDialog(ctx, comment_service, "nvim"))

    test_app = _TestApp()
    async with test_app.run_test() as pilot:
        assert isinstance(test_app.screen, CommentDialog)
        text_area = test_app.screen.query_one(TextArea)
        text_area.insert("Reply text")
        await pilot.press("ctrl+s")
        await pilot.pause(0.3)
        assert not isinstance(test_app.screen, CommentDialog)
        comment_service.reply_to_discussion.assert_called_once_with(
            mr_iid=1, discussion_id="disc123", body="Reply text"
        )


@pytest.mark.asyncio
async def test_comment_dialog_submit_api_error_shows_error_dialog() -> None:
    """API エラー時にエラーダイアログが表示されることを確認する。"""
    from textual.app import App, ComposeResult
    from textual.widgets import Label, TextArea

    from glreview.services.exceptions import GitLabConnectionError
    from glreview.tui.screens.comment_dialog import CommentDialog

    ctx = _make_note_context()
    comment_service = MagicMock()
    comment_service.add_note = AsyncMock(side_effect=GitLabConnectionError("API error"))

    class _TestApp(App):
        def compose(self) -> ComposeResult:
            yield Label("base")

        async def on_mount(self) -> None:
            await self.push_screen(CommentDialog(ctx, comment_service, "nvim"))

    test_app = _TestApp()
    async with test_app.run_test() as pilot:
        assert isinstance(test_app.screen, CommentDialog)
        text_area = test_app.screen.query_one(TextArea)
        text_area.insert("Some comment")
        await pilot.press("ctrl+s")
        await pilot.pause(0.5)
        # エラーダイアログが表示されること (GLReviewAPIError → ErrorDialog)
        from glreview.tui.screens.error_dialog import ErrorDialog

        assert isinstance(test_app.screen, ErrorDialog)
        await pilot.press("escape")


@pytest.mark.asyncio
async def test_comment_dialog_submitting_flag_prevents_double_submit() -> None:
    """二重送信フラグが正しく機能することを確認する。"""
    import asyncio

    from textual.app import App, ComposeResult
    from textual.widgets import Label, TextArea

    from glreview.tui.screens.comment_dialog import CommentDialog

    ctx = _make_note_context()
    call_count = 0

    async def slow_add_note(**kwargs):
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.2)
        return None

    comment_service = MagicMock()
    comment_service.add_note = slow_add_note

    class _TestApp(App):
        def compose(self) -> ComposeResult:
            yield Label("base")

        async def on_mount(self) -> None:
            await self.push_screen(CommentDialog(ctx, comment_service, "nvim"))

    test_app = _TestApp()
    async with test_app.run_test() as pilot:
        assert isinstance(test_app.screen, CommentDialog)
        text_area = test_app.screen.query_one(TextArea)
        text_area.insert("My comment")
        # 二重送信を試みる
        await pilot.press("ctrl+s")
        await pilot.press("ctrl+s")
        await pilot.pause(0.5)
        # add_note は1回だけ呼ばれること
        assert call_count == 1


@pytest.mark.asyncio
async def test_comment_dialog_submit_empty_comment_error_from_service() -> None:
    """サービスが EmptyCommentError を投げた場合にエラーラベルが更新されることを確認する。"""
    from textual.app import App, ComposeResult
    from textual.widgets import Label, TextArea

    from glreview.services.exceptions import EmptyCommentError
    from glreview.tui.screens.comment_dialog import CommentDialog

    ctx = _make_note_context()
    comment_service = MagicMock()
    comment_service.add_note = AsyncMock(side_effect=EmptyCommentError("empty"))

    class _TestApp(App):
        def compose(self) -> ComposeResult:
            yield Label("base")

        async def on_mount(self) -> None:
            await self.push_screen(CommentDialog(ctx, comment_service, "nvim"))

    test_app = _TestApp()
    async with test_app.run_test() as pilot:
        assert isinstance(test_app.screen, CommentDialog)
        text_area = test_app.screen.query_one(TextArea)
        text_area.insert("Not actually empty from dialog POV")
        await pilot.press("ctrl+s")
        await pilot.pause(0.3)
        # EmptyCommentError が発生してもダイアログは閉じないこと
        assert isinstance(test_app.screen, CommentDialog)


@pytest.mark.asyncio
async def test_comment_dialog_on_button_pressed_cancel_button() -> None:
    """Cancel ボタンの on_button_pressed が action_cancel を呼ぶことを確認する。"""
    from textual.app import App, ComposeResult
    from textual.widgets import Label

    from glreview.tui.screens.comment_dialog import CommentDialog

    ctx = _make_note_context()
    comment_service = MagicMock()

    class _TestApp(App):
        def compose(self) -> ComposeResult:
            yield Label("base")

        async def on_mount(self) -> None:
            await self.push_screen(CommentDialog(ctx, comment_service, "nvim"))

    test_app = _TestApp()
    async with test_app.run_test() as pilot:
        assert isinstance(test_app.screen, CommentDialog)
        # Cancel ボタン押下で on_button_pressed が実行されること確認
        await pilot.click("#cancel-button")
        await pilot.pause(0.1)
        assert not isinstance(test_app.screen, CommentDialog)
