"""TUI スクリーン/ダイアログのテスト。"""

from __future__ import annotations

import pytest


class TestStyleSelectDialogMakeOptions:
    def test_no_query_returns_all_styles(self) -> None:
        from glreview.tui.screens.style_select_dialog import (
            DEFAULT_OPTION_ID,
            _make_options,
        )

        options = _make_options("")
        # DEFAULT_OPTION_ID + Separator + all pygments styles
        ids = [opt.id for opt in options if hasattr(opt, "id") and opt.id is not None]
        assert DEFAULT_OPTION_ID in ids
        assert len(ids) >= 2

    def test_query_filters_results(self) -> None:
        from glreview.tui.screens.style_select_dialog import _make_options

        options = _make_options("monokai")
        ids = [opt.id for opt in options if hasattr(opt, "id") and opt.id is not None]
        assert "monokai" in ids

    def test_query_with_no_match_returns_only_default(self) -> None:
        from glreview.tui.screens.style_select_dialog import (
            DEFAULT_OPTION_ID,
            _make_options,
        )

        options = _make_options("xyznonexistentstyle123")
        ids = [opt.id for opt in options if hasattr(opt, "id") and opt.id is not None]
        assert DEFAULT_OPTION_ID in ids
        # Only default should match (no real style matches)
        assert len(ids) == 1


class TestSyntaxSelectDialogMakeOptions:
    def test_no_query_returns_all_languages(self) -> None:
        from glreview.tui.screens.syntax_select_dialog import (
            AUTO_OPTION_ID,
            NONE_OPTION_ID,
            _make_options,
        )

        options = _make_options("")
        ids = [opt.id for opt in options if hasattr(opt, "id") and opt.id is not None]
        assert AUTO_OPTION_ID in ids
        assert NONE_OPTION_ID in ids
        assert len(ids) > 5

    def test_query_filters_languages(self) -> None:
        from glreview.tui.screens.syntax_select_dialog import _make_options

        options = _make_options("python")
        ids = [opt.id for opt in options if hasattr(opt, "id") and opt.id is not None]
        assert "python" in ids

    def test_query_no_match_returns_only_special_options(self) -> None:
        from glreview.tui.screens.syntax_select_dialog import (
            AUTO_OPTION_ID,
            NONE_OPTION_ID,
            _make_options,
        )

        options = _make_options("xyznonexistentlang999")
        ids = [opt.id for opt in options if hasattr(opt, "id") and opt.id is not None]
        assert AUTO_OPTION_ID in ids
        assert NONE_OPTION_ID in ids
        assert len(ids) == 2


@pytest.mark.asyncio
async def test_comment_view_dialog_renders() -> None:
    """CommentViewDialog がレンダリングされてコメントが表示されることを確認する。"""
    from textual.app import App, ComposeResult
    from textual.widgets import Label

    from glreview.models import Discussion, Note
    from glreview.tui.screens.comment_view_dialog import CommentViewDialog

    note = Note(
        id=1,
        author="alice",
        body="Great work!",
        created_at="2026-01-01",
    )
    disc = Discussion(id="d1", notes=[note])

    class _TestApp(App):
        def compose(self) -> ComposeResult:
            yield Label("base")

        async def on_mount(self) -> None:
            await self.push_screen(CommentViewDialog([disc], 10, "foo.py"))

    test_app = _TestApp()
    async with test_app.run_test() as pilot:
        assert isinstance(test_app.screen, CommentViewDialog)
        await pilot.press("escape")
        assert not isinstance(test_app.screen, CommentViewDialog)


@pytest.mark.asyncio
async def test_comment_view_dialog_close_button() -> None:
    """CommentViewDialog の閉じるボタンが機能することを確認する。"""
    from textual.app import App, ComposeResult
    from textual.widgets import Label

    from glreview.models import Discussion, Note
    from glreview.tui.screens.comment_view_dialog import CommentViewDialog

    note = Note(
        id=2,
        author="bob",
        body="Line one\nLine two",
        created_at="2026-01-02",
    )
    disc = Discussion(id="d2", notes=[note])

    class _TestApp(App):
        def compose(self) -> ComposeResult:
            yield Label("base")

        async def on_mount(self) -> None:
            await self.push_screen(CommentViewDialog([disc], 5, "bar.py"))

    test_app = _TestApp()
    async with test_app.run_test() as pilot:
        assert isinstance(test_app.screen, CommentViewDialog)
        await pilot.click("#close-button")
        assert not isinstance(test_app.screen, CommentViewDialog)


@pytest.mark.asyncio
async def test_style_select_dialog_cancel() -> None:
    """StyleSelectDialog が Escape でキャンセルされることを確認する。"""
    from textual.app import App, ComposeResult
    from textual.widgets import Label

    from glreview.tui.screens.style_select_dialog import StyleSelectDialog

    class _TestApp(App):
        def compose(self) -> ComposeResult:
            yield Label("base")

        async def on_mount(self) -> None:
            await self.push_screen(StyleSelectDialog("monokai"))

    test_app = _TestApp()
    async with test_app.run_test() as pilot:
        assert isinstance(test_app.screen, StyleSelectDialog)
        await pilot.press("escape")
        assert not isinstance(test_app.screen, StyleSelectDialog)


@pytest.mark.asyncio
async def test_syntax_select_dialog_cancel() -> None:
    """SyntaxSelectDialog が Escape でキャンセルされることを確認する。"""
    from textual.app import App, ComposeResult
    from textual.widgets import Label

    from glreview.tui.screens.syntax_select_dialog import SyntaxSelectDialog

    class _TestApp(App):
        def compose(self) -> ComposeResult:
            yield Label("base")

        async def on_mount(self) -> None:
            await self.push_screen(SyntaxSelectDialog("python"))

    test_app = _TestApp()
    async with test_app.run_test() as pilot:
        assert isinstance(test_app.screen, SyntaxSelectDialog)
        await pilot.press("escape")
        assert not isinstance(test_app.screen, SyntaxSelectDialog)


@pytest.mark.asyncio
async def test_submit_review_dialog_cancel() -> None:
    """SubmitReviewDialog が Escape でキャンセルされ、publish_review が呼ばれないことを確認する。"""
    from unittest.mock import AsyncMock, MagicMock

    from textual.app import App, ComposeResult
    from textual.widgets import Label

    from glreview.models import Note
    from glreview.tui.screens.submit_review_dialog import SubmitReviewDialog

    comment_service = MagicMock()
    comment_service.publish_review = AsyncMock()
    draft = Note(id=1, author="me", body="pending", created_at="", is_draft=True)

    class _TestApp(App):
        def compose(self) -> ComposeResult:
            yield Label("base")

        async def on_mount(self) -> None:
            await self.push_screen(SubmitReviewDialog(10, [draft], comment_service))

    test_app = _TestApp()
    async with test_app.run_test() as pilot:
        assert isinstance(test_app.screen, SubmitReviewDialog)
        await pilot.press("escape")
        assert not isinstance(test_app.screen, SubmitReviewDialog)
    comment_service.publish_review.assert_not_called()


@pytest.mark.asyncio
async def test_submit_review_dialog_submit() -> None:
    """SubmitReviewDialog の送信で publish_review が呼ばれ、ReviewSubmitted が送出されることを確認する。"""  # noqa: E501
    from unittest.mock import AsyncMock, MagicMock

    from textual.app import App, ComposeResult
    from textual.widgets import Label

    from glreview.models import Note
    from glreview.tui.messages import ReviewSubmitted
    from glreview.tui.screens.submit_review_dialog import SubmitReviewDialog

    comment_service = MagicMock()
    comment_service.publish_review = AsyncMock()
    draft = Note(id=1, author="me", body="pending", created_at="", is_draft=True)
    received: list[ReviewSubmitted] = []

    class _TestApp(App):
        def compose(self) -> ComposeResult:
            yield Label("base")

        async def on_mount(self) -> None:
            await self.push_screen(SubmitReviewDialog(10, [draft], comment_service))

        def on_review_submitted(self, message: ReviewSubmitted) -> None:
            received.append(message)

    test_app = _TestApp()
    async with test_app.run_test() as pilot:
        assert isinstance(test_app.screen, SubmitReviewDialog)
        await pilot.click("#submit-button")
        await pilot.pause()
        assert not isinstance(test_app.screen, SubmitReviewDialog)
    comment_service.publish_review.assert_awaited_once_with(10)
    assert len(received) == 1
    assert received[0].mr_iid == 10
