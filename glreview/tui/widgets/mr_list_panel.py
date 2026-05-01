"""MRListPanel — 左ペインのMR一覧ツリーウィジェット。"""

from __future__ import annotations

import asyncio
from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import Binding
from textual.widget import Widget
from textual.widgets import Tree
from textual.widgets._tree import TreeNode

from glreview.infrastructure.logger import get_logger
from glreview.services import CommentService, MRService
from glreview.services.exceptions import GLReviewAPIError
from glreview.services.types import MRCategory
from glreview.tui.entities import (
    CATEGORY_LABELS,
    TreeNodeData,
    TreeNodeType,
    get_file_change_label,
)
from glreview.tui.messages import ShowDiff, ShowOverview
from glreview.tui.screens.error_dialog import ErrorDialog

_logger = get_logger(__name__)


class MRListPanel(Widget):
    """左ペイン: MRをカテゴリ別ツリーで表示するウィジェット。"""

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("h", "scroll_left", "Left", show=False),
        Binding("l", "scroll_right", "Right", show=False),
    ]

    DEFAULT_CSS = """
    MRListPanel {
        width: 30%;
        height: 100%;
    }
    """

    def __init__(self, mr_service: MRService, comment_service: CommentService) -> None:
        super().__init__()
        self._mr_service = mr_service
        self._comment_service = comment_service
        self._category_pages: dict[MRCategory, int] = dict.fromkeys(MRCategory, 1)
        self._selected_mr_iid: int | None = None
        # mr_iid ではなくノードオブジェクト自体で追跡する
        # （同一 MR が複数カテゴリに存在する場合に独立して展開できるようにするため）
        self._expanded_nodes: set[TreeNode] = set()
        self._loading_nodes: set[TreeNode] = set()
        # カテゴリノードへの参照を保持
        self._category_nodes: dict[MRCategory, TreeNode[TreeNodeData]] = {}

    def compose(self) -> ComposeResult:
        yield Tree("Merge Requests", id="mr-tree")

    def on_mount(self) -> None:
        self.run_worker(self._load_all_categories(), exclusive=True)

    async def _load_all_categories(self) -> None:
        """5カテゴリを並行取得してツリーを構築する。"""
        tree = self.query_one(Tree)
        tree.root.expand()

        self.app.sub_title = "Loading MR list..."
        try:
            results = await asyncio.gather(
                self._mr_service.get_assigned_to_me(page=1),
                self._mr_service.get_reviewer_is_me(page=1),
                self._mr_service.get_created_by_me(page=1),
                self._mr_service.get_unassigned(page=1),
                self._mr_service.get_assigned_to_others(page=1),
                return_exceptions=True,
            )
        finally:
            self.app.sub_title = ""

        categories = [
            MRCategory.ASSIGNED_TO_ME,
            MRCategory.REVIEWER_IS_ME,
            MRCategory.CREATED_BY_ME,
            MRCategory.UNASSIGNED,
            MRCategory.ASSIGNED_TO_OTHERS,
        ]

        expands = [False, True, False, False, False]

        for category, result, expand in zip(categories, results, expands, strict=False):
            if isinstance(result, Exception):
                _logger.error("Failed to load %s: %s", category, result)
                label = f"{CATEGORY_LABELS[category]} (error)"
                node = tree.root.add(
                    label,
                    data=TreeNodeData(node_type=TreeNodeType.CATEGORY, category=category),
                    expand=expand,
                )
                self._category_nodes[category] = node
                continue

            paginated = result
            count = len(paginated.items)
            label = f"{CATEGORY_LABELS[category]} ({count})"
            cat_node = tree.root.add(
                label,
                data=TreeNodeData(node_type=TreeNodeType.CATEGORY, category=category),
                expand=expand,
            )
            self._category_nodes[category] = cat_node

            if count == 0:
                cat_node.add_leaf(
                    "(empty)",
                    data=TreeNodeData(node_type=TreeNodeType.CATEGORY, category=category),
                )
            else:
                for mr in paginated.items:
                    cat_node.add_leaf(
                        f"!{mr.iid} {mr.title}",
                        data=TreeNodeData(node_type=TreeNodeType.MR, mr_iid=mr.iid),
                    )
                if paginated.has_next_page and paginated.next_page is not None:
                    self._category_pages[category] = paginated.next_page
                    cat_node.add_leaf(
                        "Load more...",
                        data=TreeNodeData(
                            node_type=TreeNodeType.LOAD_MORE,
                            category=category,
                            next_page=paginated.next_page,
                        ),
                    )
        tree.focus()

    async def _expand_mr(self, node: TreeNode[TreeNodeData], mr_iid: int) -> None:
        """MRノードを展開してファイル一覧を表示する。"""
        self.app.sub_title = f"Loading MR !{mr_iid}..."
        try:
            changes, discussions = await asyncio.gather(
                self._mr_service.get_mr_changes(mr_iid),
                self._comment_service.get_discussions(mr_iid),
                return_exceptions=False,
            )
        except GLReviewAPIError as exc:
            _logger.error("Failed to load MR changes for !%d: %s", mr_iid, exc.message)
            self._loading_nodes.discard(node)
            await self.app.push_screen(ErrorDialog(exc.message))
            return
        finally:
            self.app.sub_title = ""

        # インラインコメントがあるファイルパスを収集する
        # file_path が空文字の場合は追加しない（new_file の old_path="" などと誤マッチを防ぐ）
        comment_files: set[str] = set()
        for disc in discussions:
            for note in disc.notes:
                if note.position is not None and note.position.file_path:
                    comment_files.add(note.position.file_path)

        self._expanded_nodes.add(node)
        self._loading_nodes.discard(node)

        # Overview ノード
        node.add_leaf(
            "Overview",
            data=TreeNodeData(node_type=TreeNodeType.OVERVIEW, mr_iid=mr_iid),
        )
        # ファイルノード
        for change in changes:
            label = get_file_change_label(
                old_path=change.old_path,
                new_path=change.new_path,
                new_file=change.new_file,
                deleted_file=change.deleted_file,
                renamed_file=change.renamed_file,
            )
            if change.new_path in comment_files or (
                change.old_path and change.old_path in comment_files
            ):
                label = "💬 " + label
            node.add_leaf(
                label,
                data=TreeNodeData(
                    node_type=TreeNodeType.FILE,
                    mr_iid=mr_iid,
                    file_path=change.new_path,
                ),
            )
        node.expand()

    async def _load_more(self, node: TreeNode[TreeNodeData]) -> None:
        """追加ページを取得してノードを追加する。"""
        data = node.data
        if data is None or data.category is None or data.next_page is None:
            return

        category = data.category
        page = data.next_page
        self.app.sub_title = f"Loading more {CATEGORY_LABELS[category]}..."

        try:
            result = await self._mr_service._get_mr_list_by_category(category, page=page)
        except GLReviewAPIError as exc:
            _logger.error("Failed to load more MRs: %s", exc.message)
            await self.app.push_screen(ErrorDialog(exc.message))
            return
        except AttributeError:
            # _get_mr_list_by_category が存在しない場合のフォールバック
            _logger.warning("Category load more not available for %s", category)
            return
        finally:
            self.app.sub_title = ""

        parent = node.parent
        if parent is None:
            return

        # "Load more..." ノードを削除してMRを追加
        node.remove()

        for mr in result.items:
            parent.add_leaf(
                f"!{mr.iid} {mr.title}",
                data=TreeNodeData(node_type=TreeNodeType.MR, mr_iid=mr.iid),
            )

        if result.has_next_page and result.next_page is not None:
            self._category_pages[category] = result.next_page
            parent.add_leaf(
                "Load more...",
                data=TreeNodeData(
                    node_type=TreeNodeType.LOAD_MORE,
                    category=category,
                    next_page=result.next_page,
                ),
            )

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        """ツリーノード選択イベントを処理する。"""
        node = event.node
        data: TreeNodeData | None = node.data
        if data is None:
            return

        if data.node_type == TreeNodeType.CATEGORY:
            return

        if data.node_type == TreeNodeType.MR:
            mr_iid = data.mr_iid
            if mr_iid is None:
                return
            if node in self._expanded_nodes:
                # 既に展開済み: toggle で開閉する
                node.toggle()
                return
            if node in self._loading_nodes:
                # 読み込み中: 二重展開を防ぐ
                return
            self._loading_nodes.add(node)
            self.run_worker(self._expand_mr(node, mr_iid), exclusive=False)
            return

        if data.node_type == TreeNodeType.OVERVIEW:
            if data.mr_iid is not None:
                self.post_message(ShowOverview(data.mr_iid))
            return

        if data.node_type == TreeNodeType.FILE:
            if data.mr_iid is not None and data.file_path is not None:
                self.post_message(ShowDiff(data.mr_iid, data.file_path))
            return

        if data.node_type == TreeNodeType.LOAD_MORE:
            self.run_worker(self._load_more(node), exclusive=False)

    def get_selected_mr_iid(self) -> int | None:
        """現在カーソルがあるノードの MR IID を返す。取得できない場合は None。"""
        tree = self.query_one(Tree)
        node = tree.cursor_node
        if node is None or node.data is None:
            return None
        return node.data.mr_iid

    def action_cursor_down(self) -> None:
        self.query_one(Tree).action_cursor_down()

    def action_cursor_up(self) -> None:
        self.query_one(Tree).action_cursor_up()

    def action_scroll_left(self) -> None:
        self.query_one(Tree).scroll_left(animate=False)

    def action_scroll_right(self) -> None:
        self.query_one(Tree).scroll_right(animate=False)

    async def refresh_list(self) -> None:
        """MR一覧を再取得する（リフレッシュ時）。"""
        tree = self.query_one(Tree)
        tree.root.remove_children()
        self._category_nodes.clear()
        self._expanded_nodes.clear()
        self._loading_nodes.clear()
        self._category_pages = dict.fromkeys(MRCategory, 1)
        await self._load_all_categories()
