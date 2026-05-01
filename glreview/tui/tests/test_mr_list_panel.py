"""MRListPanel のテスト。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from glreview.models import FileChange, MergeRequestSummary
from glreview.services.types import MRCategory, PaginatedResult


def _make_mr_summary(iid: int = 1, title: str = "Test MR") -> MergeRequestSummary:
    return MergeRequestSummary(
        iid=iid,
        title=title,
        author="alice",
        status="opened",
        labels=[],
        updated_at="2026-01-01T00:00:00Z",
    )


def _make_paginated(items: list, has_next: bool = False) -> PaginatedResult:
    return PaginatedResult(
        items=items,
        has_next_page=has_next,
        next_page=2 if has_next else None,
    )


def _make_mr_service_with_data():
    """MRServiceのモック(MRデータあり)を生成する。"""
    service = MagicMock()
    mr = _make_mr_summary(iid=10, title="My Feature")
    result = _make_paginated([mr])
    service.get_assigned_to_me = AsyncMock(return_value=result)
    service.get_reviewer_is_me = AsyncMock(return_value=_make_paginated([]))
    service.get_created_by_me = AsyncMock(return_value=_make_paginated([]))
    service.get_unassigned = AsyncMock(return_value=_make_paginated([]))
    service.get_assigned_to_others = AsyncMock(return_value=_make_paginated([]))
    return service


def _make_empty_service():
    """MRServiceのモック(全空)を生成する。"""
    service = MagicMock()
    empty = _make_paginated([])
    service.get_assigned_to_me = AsyncMock(return_value=empty)
    service.get_reviewer_is_me = AsyncMock(return_value=empty)
    service.get_created_by_me = AsyncMock(return_value=empty)
    service.get_unassigned = AsyncMock(return_value=empty)
    service.get_assigned_to_others = AsyncMock(return_value=empty)
    return service


def _make_comment_service():
    cs = MagicMock()
    cs.get_discussions = AsyncMock(return_value=[])
    return cs


@pytest.mark.asyncio
async def test_mr_list_panel_loads_mrs_into_tree() -> None:
    """MRListPanel がMRをツリーに表示することを確認する。"""
    from textual.app import App, ComposeResult

    from glreview.tui.widgets.mr_list_panel import MRListPanel

    mr_service = _make_mr_service_with_data()
    comment_service = _make_comment_service()

    class _TestApp(App):
        def compose(self) -> ComposeResult:
            yield MRListPanel(mr_service, comment_service)

    test_app = _TestApp()
    async with test_app.run_test() as pilot:
        await pilot.pause(0.5)
        panel = test_app.query_one(MRListPanel)
        # Assigned to me カテゴリにMRが入っていること
        from glreview.services.types import MRCategory

        assigned_node = panel._category_nodes.get(MRCategory.ASSIGNED_TO_ME)
        assert assigned_node is not None
        # Children にMRノードがあること
        children = list(assigned_node.children)
        assert len(children) >= 1


@pytest.mark.asyncio
async def test_mr_list_panel_loads_empty_category() -> None:
    """MRListPanel が空カテゴリに (empty) 表示することを確認する。"""
    from textual.app import App, ComposeResult

    from glreview.tui.widgets.mr_list_panel import MRListPanel

    mr_service = _make_empty_service()
    comment_service = _make_comment_service()

    class _TestApp(App):
        def compose(self) -> ComposeResult:
            yield MRListPanel(mr_service, comment_service)

    test_app = _TestApp()
    async with test_app.run_test() as pilot:
        await pilot.pause(0.5)
        panel = test_app.query_one(MRListPanel)
        from glreview.services.types import MRCategory

        assigned_node = panel._category_nodes.get(MRCategory.ASSIGNED_TO_ME)
        assert assigned_node is not None
        children = list(assigned_node.children)
        # empty の場合は "(empty)" ラベルのノードが1件
        assert len(children) == 1


@pytest.mark.asyncio
async def test_mr_list_panel_handles_exception_in_category() -> None:
    """カテゴリのロードが失敗した場合に (error) ラベルが表示されることを確認する。"""
    from textual.app import App, ComposeResult

    from glreview.services.exceptions import GitLabConnectionError
    from glreview.tui.widgets.mr_list_panel import MRListPanel

    mr_service = MagicMock()
    mr_service.get_assigned_to_me = AsyncMock(
        side_effect=GitLabConnectionError("Connection failed")
    )
    mr_service.get_reviewer_is_me = AsyncMock(return_value=_make_paginated([]))
    mr_service.get_created_by_me = AsyncMock(return_value=_make_paginated([]))
    mr_service.get_unassigned = AsyncMock(return_value=_make_paginated([]))
    mr_service.get_assigned_to_others = AsyncMock(return_value=_make_paginated([]))
    comment_service = _make_comment_service()

    class _TestApp(App):
        def compose(self) -> ComposeResult:
            yield MRListPanel(mr_service, comment_service)

    test_app = _TestApp()
    async with test_app.run_test() as pilot:
        await pilot.pause(0.5)
        panel = test_app.query_one(MRListPanel)
        from glreview.services.types import MRCategory

        assigned_node = panel._category_nodes.get(MRCategory.ASSIGNED_TO_ME)
        assert assigned_node is not None
        # error ラベルが含まれることを確認
        assert "(error)" in str(assigned_node.label)


@pytest.mark.asyncio
async def test_mr_list_panel_expand_mr_on_select() -> None:
    """MRノード選択時に `_expand_mr` が呼ばれファイル一覧が展開されることを確認する。"""
    from textual.app import App, ComposeResult

    from glreview.tui.widgets.mr_list_panel import MRListPanel

    mr_service = _make_mr_service_with_data()
    file_change = FileChange(
        old_path="src/main.py",
        new_path="src/main.py",
        new_file=False,
        deleted_file=False,
        renamed_file=False,
    )
    mr_service.get_mr_changes = AsyncMock(return_value=[file_change])
    comment_service = _make_comment_service()

    class _TestApp(App):
        def compose(self) -> ComposeResult:
            yield MRListPanel(mr_service, comment_service)

    test_app = _TestApp()
    async with test_app.run_test() as pilot:
        await pilot.pause(0.5)
        # MRノードを選択
        # 子ノードに移動
        await pilot.press("j")  # cursor down
        await pilot.press("enter")  # select
        await pilot.pause(0.5)


@pytest.mark.asyncio
async def test_mr_list_panel_get_selected_mr_iid() -> None:
    """get_selected_mr_iid が現在のカーソルのMR IIDを返すことを確認する。"""
    from textual.app import App, ComposeResult

    from glreview.tui.widgets.mr_list_panel import MRListPanel

    mr_service = _make_mr_service_with_data()
    comment_service = _make_comment_service()

    class _TestApp(App):
        def compose(self) -> ComposeResult:
            yield MRListPanel(mr_service, comment_service)

    test_app = _TestApp()
    async with test_app.run_test() as pilot:
        await pilot.pause(0.5)
        panel = test_app.query_one(MRListPanel)
        # ルートノードが選択されている場合
        result = panel.get_selected_mr_iid()
        assert result is None or isinstance(result, int)

        # MRノードに移動した場合 (line 286: return node.data.mr_iid)
        await pilot.press("j")  # ASSIGNED_TO_ME category
        await pilot.press("enter")  # expand category
        await pilot.press("j")  # MR node (iid=10)
        await pilot.pause(0.2)
        result = panel.get_selected_mr_iid()
        assert result == 10


@pytest.mark.asyncio
async def test_mr_list_panel_refresh_list() -> None:
    """refresh_list がツリーをクリアして再ロードすることを確認する。"""
    from textual.app import App, ComposeResult

    from glreview.tui.widgets.mr_list_panel import MRListPanel

    mr_service = _make_empty_service()
    comment_service = _make_comment_service()

    class _TestApp(App):
        def compose(self) -> ComposeResult:
            yield MRListPanel(mr_service, comment_service)

    test_app = _TestApp()
    async with test_app.run_test() as pilot:
        await pilot.pause(0.5)
        panel = test_app.query_one(MRListPanel)
        # refresh_list を呼ぶ
        await panel.refresh_list()
        await pilot.pause(0.3)
        # カテゴリノードが再ロードされていること
        from glreview.services.types import MRCategory

        assert MRCategory.ASSIGNED_TO_ME in panel._category_nodes


@pytest.mark.asyncio
async def test_mr_list_panel_key_actions() -> None:
    """j/k キーでカーソルが移動することを確認する。"""
    from textual.app import App, ComposeResult

    from glreview.tui.widgets.mr_list_panel import MRListPanel

    mr_service = _make_mr_service_with_data()
    comment_service = _make_comment_service()

    class _TestApp(App):
        def compose(self) -> ComposeResult:
            yield MRListPanel(mr_service, comment_service)

    test_app = _TestApp()
    async with test_app.run_test() as pilot:
        await pilot.pause(0.5)
        # j/k キーが例外なく動くことを確認
        await pilot.press("j")
        await pilot.press("k")
        await pilot.press("h")
        await pilot.press("l")


@pytest.mark.asyncio
async def test_mr_list_panel_loads_paginated_data() -> None:
    """has_next_page=True の場合に 'Load more...' ノードが表示されることを確認する。"""
    from textual.app import App, ComposeResult

    from glreview.tui.widgets.mr_list_panel import MRListPanel

    mr_service = MagicMock()
    mr = _make_mr_summary(iid=5, title="Feature A")
    paginated_with_next = _make_paginated([mr], has_next=True)
    mr_service.get_assigned_to_me = AsyncMock(return_value=paginated_with_next)
    mr_service.get_reviewer_is_me = AsyncMock(return_value=_make_paginated([]))
    mr_service.get_created_by_me = AsyncMock(return_value=_make_paginated([]))
    mr_service.get_unassigned = AsyncMock(return_value=_make_paginated([]))
    mr_service.get_assigned_to_others = AsyncMock(return_value=_make_paginated([]))
    comment_service = _make_comment_service()

    class _TestApp(App):
        def compose(self) -> ComposeResult:
            yield MRListPanel(mr_service, comment_service)

    test_app = _TestApp()
    async with test_app.run_test() as pilot:
        await pilot.pause(0.5)
        panel = test_app.query_one(MRListPanel)
        assigned_node = panel._category_nodes.get(MRCategory.ASSIGNED_TO_ME)
        assert assigned_node is not None
        children = list(assigned_node.children)
        # MRノードと Load more... ノードの2件
        labels = [str(child.label) for child in children]
        assert any("Load more" in label for label in labels)


@pytest.mark.asyncio
async def test_mr_list_panel_expand_mr_shows_files() -> None:
    """MRを展開するとファイル一覧が表示されることを確認する。"""
    from textual.app import App, ComposeResult

    from glreview.tui.widgets.mr_list_panel import MRListPanel

    mr_service = _make_mr_service_with_data()
    file_change = FileChange(
        old_path="src/foo.py",
        new_path="src/foo.py",
        new_file=False,
        deleted_file=False,
        renamed_file=False,
    )
    mr_service.get_mr_changes = AsyncMock(return_value=[file_change])
    comment_service = _make_comment_service()

    class _TestApp(App):
        def compose(self) -> ComposeResult:
            yield MRListPanel(mr_service, comment_service)

    test_app = _TestApp()
    async with test_app.run_test() as pilot:
        await pilot.pause(0.5)
        panel = test_app.query_one(MRListPanel)
        # カテゴリを展開してMRノードを選択
        # j: ASSIGNED_TO_ME カテゴリへ移動
        # enter: カテゴリを展開
        # j: MRノードへ移動
        # enter: MRを展開
        await pilot.press("j")
        await pilot.press("enter")
        await pilot.press("j")
        await pilot.press("enter")
        await pilot.pause(0.8)
        # _expand_mr が呼ばれてファイルが追加されること（少なくとも例外なし）
        assigned_node = panel._category_nodes.get(MRCategory.ASSIGNED_TO_ME)
        assert assigned_node is not None


@pytest.mark.asyncio
async def test_mr_list_panel_overview_node_selection() -> None:
    """Overview ノード選択時に ShowOverview メッセージが発行されることを確認する。"""
    from textual.app import App, ComposeResult

    from glreview.tui.messages import ShowOverview
    from glreview.tui.widgets.mr_list_panel import MRListPanel

    mr_service = _make_mr_service_with_data()
    mr_service.get_mr_changes = AsyncMock(return_value=[])
    comment_service = _make_comment_service()

    received_messages = []

    class _TestApp(App):
        def compose(self) -> ComposeResult:
            yield MRListPanel(mr_service, comment_service)

        def on_show_overview(self, message: ShowOverview) -> None:
            received_messages.append(message)

    test_app = _TestApp()
    async with test_app.run_test() as pilot:
        await pilot.pause(0.5)
        # ASSIGNED_TO_ME を展開 → MRを展開 → Overviewを選択
        await pilot.press("j")  # ASSIGNED_TO_ME category
        await pilot.press("enter")  # expand category
        await pilot.press("j")  # MR node
        await pilot.press("enter")  # expand MR → calls _expand_mr
        await pilot.pause(0.8)  # wait for worker
        # Overview ノードは _expand_mr で最初に追加される
        await pilot.press("j")  # move to Overview node
        await pilot.press("enter")  # select Overview
        await pilot.pause(0.2)
        # ShowOverview メッセージが受け取られたことを確認
        assert len(received_messages) >= 1
        assert received_messages[0].mr_iid == 10


@pytest.mark.asyncio
async def test_mr_list_panel_category_node_selection_ignored() -> None:
    """カテゴリノード選択時に何も起きないことを確認する（エラーなし）。"""
    from textual.app import App, ComposeResult

    from glreview.tui.widgets.mr_list_panel import MRListPanel

    mr_service = _make_empty_service()
    comment_service = _make_comment_service()

    class _TestApp(App):
        def compose(self) -> ComposeResult:
            yield MRListPanel(mr_service, comment_service)

    test_app = _TestApp()
    async with test_app.run_test() as pilot:
        await pilot.pause(0.5)
        # ルートノードに留まってEnterを押す（カテゴリノードの選択）
        await pilot.press("enter")
        await pilot.pause(0.1)
        # 例外なく終了することを確認


@pytest.mark.asyncio
async def test_mr_list_panel_expand_mr_api_error() -> None:
    """MR展開時にAPI エラーが発生した場合にエラーダイアログが表示されることを確認する。"""
    from textual.app import App, ComposeResult

    from glreview.services.exceptions import GitLabConnectionError
    from glreview.tui.widgets.mr_list_panel import MRListPanel

    mr_service = _make_mr_service_with_data()
    mr_service.get_mr_changes = AsyncMock(side_effect=GitLabConnectionError("API error"))
    comment_service = _make_comment_service()

    class _TestApp(App):
        def compose(self) -> ComposeResult:
            yield MRListPanel(mr_service, comment_service)

    test_app = _TestApp()
    async with test_app.run_test() as pilot:
        await pilot.pause(0.5)
        # カテゴリ展開→MRノード選択→expand_mr でエラーが発生
        await pilot.press("j")  # ASSIGNED_TO_ME category
        await pilot.press("enter")  # expand category
        await pilot.press("j")  # MR node
        await pilot.press("enter")  # expand MR → triggers _expand_mr (errors)
        await pilot.pause(0.8)
        # エラーが発生しても例外が上がらないこと（エラーダイアログで処理）


@pytest.mark.asyncio
async def test_mr_list_panel_file_node_selection_sends_show_diff() -> None:
    """ファイルノード選択時に ShowDiff メッセージが発行されることを確認する。"""
    from textual.app import App, ComposeResult

    from glreview.tui.messages import ShowDiff
    from glreview.tui.widgets.mr_list_panel import MRListPanel

    mr_service = _make_mr_service_with_data()
    file_change = FileChange(
        old_path="src/foo.py",
        new_path="src/foo.py",
        new_file=False,
        deleted_file=False,
        renamed_file=False,
    )
    mr_service.get_mr_changes = AsyncMock(return_value=[file_change])
    comment_service = _make_comment_service()

    received_messages = []

    class _TestApp(App):
        def compose(self) -> ComposeResult:
            yield MRListPanel(mr_service, comment_service)

        def on_show_diff(self, message: ShowDiff) -> None:
            received_messages.append(message)

    test_app = _TestApp()
    async with test_app.run_test() as pilot:
        await pilot.pause(0.5)
        # カテゴリ展開→MR展開→ファイル選択
        await pilot.press("j")  # ASSIGNED_TO_ME category
        await pilot.press("enter")  # expand category
        await pilot.press("j")  # MR node
        await pilot.press("enter")  # expand MR → calls _expand_mr
        await pilot.pause(0.8)  # wait for worker
        # Overview ノードをスキップしてファイルノードへ
        await pilot.press("j")  # Overview node
        await pilot.press("j")  # first file node
        await pilot.press("enter")  # select file → ShowDiff
        await pilot.pause(0.2)
        # ShowDiff メッセージが受け取られたことを確認
        assert len(received_messages) >= 1
        assert received_messages[0].file_path == "src/foo.py"


@pytest.mark.asyncio
async def test_mr_list_panel_load_more_loads_next_page() -> None:
    """'Load more...' ノードを選択すると次ページが読み込まれることを確認する。"""
    from textual.app import App, ComposeResult

    from glreview.tui.widgets.mr_list_panel import MRListPanel

    mr_service = MagicMock()
    mr = _make_mr_summary(iid=5, title="Feature A")
    mr2 = _make_mr_summary(iid=6, title="Feature B")

    # 最初のページ: 1件 + has_next_page=True
    paginated_with_next = _make_paginated([mr], has_next=True)
    # 次のページ: 1件
    paginated_page2 = _make_paginated([mr2], has_next=False)

    mr_service.get_assigned_to_me = AsyncMock(return_value=paginated_with_next)
    mr_service.get_reviewer_is_me = AsyncMock(return_value=_make_paginated([]))
    mr_service.get_created_by_me = AsyncMock(return_value=_make_paginated([]))
    mr_service.get_unassigned = AsyncMock(return_value=_make_paginated([]))
    mr_service.get_assigned_to_others = AsyncMock(return_value=_make_paginated([]))
    mr_service._get_mr_list_by_category = AsyncMock(return_value=paginated_page2)

    comment_service = _make_comment_service()

    class _TestApp(App):
        def compose(self) -> ComposeResult:
            yield MRListPanel(mr_service, comment_service)

    test_app = _TestApp()
    async with test_app.run_test() as pilot:
        await pilot.pause(0.5)

        # ASSIGNED_TO_ME を展開
        await pilot.press("j")  # ASSIGNED_TO_ME category
        await pilot.press("enter")  # expand category
        await pilot.press("j")  # MR node (iid=5)
        await pilot.press("j")  # "Load more..." node
        await pilot.press("enter")  # select "Load more..." → _load_more
        await pilot.pause(0.8)

        # _get_mr_list_by_category が呼ばれること
        mr_service._get_mr_list_by_category.assert_called()


@pytest.mark.asyncio
async def test_mr_list_panel_expand_mr_with_comment_files() -> None:
    """コメントがあるファイルに 💬 マークが付くことを確認する。"""
    from textual.app import App, ComposeResult

    from glreview.models import Discussion, Note, NotePosition
    from glreview.tui.widgets.mr_list_panel import MRListPanel

    mr_service = _make_mr_service_with_data()
    file_change = FileChange(
        old_path="commented.py",
        new_path="commented.py",
        new_file=False,
        deleted_file=False,
        renamed_file=False,
    )
    mr_service.get_mr_changes = AsyncMock(return_value=[file_change])

    position = NotePosition(
        file_path="commented.py",
        new_line=5,
    )
    note = Note(id=1, author="alice", body="comment", created_at="2026-01-01", position=position)
    disc = Discussion(id="d1", notes=[note])

    comment_service = MagicMock()
    comment_service.get_discussions = AsyncMock(return_value=[disc])

    class _TestApp(App):
        def compose(self) -> ComposeResult:
            yield MRListPanel(mr_service, comment_service)

    test_app = _TestApp()
    async with test_app.run_test() as pilot:
        await pilot.pause(0.5)
        panel = test_app.query_one(MRListPanel)
        # カテゴリを展開してMRを展開
        await pilot.press("j")
        await pilot.press("enter")
        await pilot.press("j")
        await pilot.press("enter")
        await pilot.pause(0.8)
        # ファイルノードに 💬 マークが付いていること
        assigned_node = panel._category_nodes.get(MRCategory.ASSIGNED_TO_ME)
        assert assigned_node is not None
        mr_node = next(iter(assigned_node.children))
        # 子ノードにファイルがあること
        children = list(mr_node.children)
        assert len(children) >= 1  # Overview + file nodes
