"""ContentPanel — 右ペインのコンテンツ表示ウィジェット。"""

from __future__ import annotations

import re
from typing import Any, ClassVar

from pygments import lex as _pygments_lex
from rich.markdown import Markdown as RichMarkdown
from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widget import Widget
from textual.widgets import DataTable, RichLog, Static

from glreview.infrastructure.logger import get_logger
from glreview.models import CommentContext, CommentType, Discussion
from glreview.services import CommentService, MRService
from glreview.services.exceptions import GLReviewAPIError
from glreview.tui.entities import ContentViewState, DiffViewMode
from glreview.tui.messages import CommentPosted, ReviewSubmitted, ShowDiff, ShowOverview
from glreview.tui.screens.comment_dialog import CommentDialog
from glreview.tui.screens.comment_view_dialog import CommentViewDialog
from glreview.tui.screens.error_dialog import ErrorDialog
from glreview.tui.screens.style_select_dialog import (
    DEFAULT_OPTION_ID as _STYLE_DEFAULT,
)
from glreview.tui.screens.style_select_dialog import (
    StyleSelectDialog,
)
from glreview.tui.screens.submit_review_dialog import SubmitReviewDialog
from glreview.tui.screens.syntax_select_dialog import (
    AUTO_OPTION_ID as _SYNTAX_AUTO,
)
from glreview.tui.screens.syntax_select_dialog import (
    NONE_OPTION_ID as _SYNTAX_NONE,
)
from glreview.tui.screens.syntax_select_dialog import (
    SyntaxSelectDialog,
)
from glreview.tui.widgets._diff_parser import (
    _BOTTOM_LOAD_SENTINEL,
    _CONTEXT_LINES,
    _LOAD_MORE_LINES,
    _TOP_LOAD_SENTINEL,
    _apply_context_filter,
    _find_first_last_new_line,
    _parse_diff,
)
from glreview.tui.widgets._diff_renderer import (
    _DIFF_ADD_STYLE,
    _DIFF_GAP_STYLE,
    _DIFF_REM_STYLE,
    _LINE_NO_WIDTH,
    DiffGutter,
    _wrap_text,
)
from glreview.tui.widgets._overview import (
    _build_comment_map,
    _build_overview_text,
    _drafts_as_discussions,
    _get_comment_lines,
)
from glreview.tui.widgets._syntax import (
    _SYNTAX_COLORS,
    _build_colors_from_pygments_style,
    _get_lexer_for_path,
)

_logger = get_logger(__name__)


class ContentPanel(Widget):
    """右ペイン: Overview・差分をレンダリングするウィジェット。"""

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("t", "toggle_diff_mode", "Toggle unified/side-by-side", priority=True),
        Binding("c", "add_comment", "Add Comment", priority=True),
        Binding("R", "submit_review", "Submit Review", priority=True),
        Binding("w", "toggle_wrap", "Wrap", priority=True),
        Binding("s", "select_syntax", "Syntax", priority=True),
        Binding("p", "select_style", "Style", priority=True),
        Binding("a", "expand_all_lines", "All lines", priority=True),
        Binding("right_square_bracket", "jump_next_diff_line", "Next diff", priority=True),
        Binding("left_square_bracket", "jump_prev_diff_line", "Prev diff", priority=True),
        Binding("j", "diff_cursor_down", "Down", show=False),
        Binding("k", "diff_cursor_up", "Up", show=False),
        Binding("h", "diff_scroll_left", "Left", show=False),
        Binding("l", "diff_scroll_right", "Right", show=False),
    ]

    DEFAULT_CSS = """
    ContentPanel {
        width: 1fr;
        height: 100%;
    }
    """

    def __init__(self, mr_service: MRService, comment_service: CommentService) -> None:
        super().__init__()
        self._mr_service = mr_service
        self._comment_service = comment_service
        self._view_state = ContentViewState.EMPTY
        self._diff_mode = DiffViewMode.UNIFIED
        self._current_mr_iid: int | None = None
        self._current_file_path: str | None = None
        self._selected_line: int | None = None
        self._selected_old_line: int | None = None
        self._diff_row_lines: list[int | None] = []
        self._diff_row_old_lines: dict[int, int] = {}
        self._comment_lines: set[int] = set()
        self._editor_command: str = "vi"
        self._wrap_lines: bool = False
        # シンタックスハイライト用レキサー
        self._syntax_lexer: Any | None = None
        # Pygments カラースタイル（空文字 = 内蔵 Dracula パレット）
        self._pygments_style: str = ""
        self._syntax_colors: dict[Any, str] = _SYNTAX_COLORS
        # スタイル変更時に呼び出すコールバック（config への保存用）
        self._on_style_saved: Any = None
        # コメント閲覧用
        self._discussions: list[Discussion] = []
        self._comment_map: dict[int, list[Discussion]] = {}
        # ギャップ展開用
        self._current_diff_text: str = ""
        self._full_parsed_diff: list[tuple[str, int | None, int | None, str]] = []
        self._forced_ctx_indices: set[int] = set()
        self._gap_row_ranges: dict[int, tuple[int, int]] = {}
        # gap行のアクション種別 ("all"|"above"|"below"|"top_load"|"bottom_load"
        #                       |"inter_above"|"inter_below"|"inter_all")
        self._gap_row_actions: dict[int, str] = {}
        # ハンク間ギャップの読み込み状態: (prev_end, next_start) -> (above_count, below_count)
        self._inter_hunk_loaded: dict[tuple[int, int], tuple[int, int]] = {}
        # ファイル上下追加読み込み用
        self._file_content: list[str] = []
        self._top_extra_count: int = 0
        self._bottom_extra_count: int = 0
        self._first_diff_new_line: int = 0
        self._last_diff_new_line: int = 0
        # ジャンプ用: 各テーブル行の差分タイプ ("add"/"rem"/"ctx" 等)
        self._diff_row_types: list[str] = []
        # 折り返しモード時のコンテンツ列テキスト幅（_render_diff で更新）
        self._code_wrap_width: int = 40

    def compose(self) -> ComposeResult:
        yield Static("Select an MR from the list.", id="empty-hint")
        yield RichLog(id="content-log", highlight=False, markup=True, wrap=False)
        with Horizontal(id="unified-container"):
            yield DataTable(
                id="diff-table", cursor_type="row", show_header=True, zebra_stripes=False
            )
            yield DiffGutter(id="diff-gutter")
        with Horizontal(id="sbs-container"):
            yield DataTable(
                id="diff-table-left", cursor_type="row", show_header=True, zebra_stripes=False
            )
            yield DataTable(
                id="diff-table-right", cursor_type="row", show_header=True, zebra_stripes=False
            )
            yield DiffGutter(id="diff-gutter-sbs")

    def on_mount(self) -> None:
        self.query_one(RichLog).display = False
        self.query_one("#unified-container").display = False
        self.query_one("#sbs-container").display = False

        # SBS モードの横・縦スクロール同期を設定する
        left = self.query_one("#diff-table-left", DataTable)
        right = self.query_one("#diff-table-right", DataTable)

        def _sync_right_x(value: float) -> None:
            self._sync_sbs_scroll(right, "scroll_target_x", value)

        def _sync_left_x(value: float) -> None:
            self._sync_sbs_scroll(left, "scroll_target_x", value)

        def _sync_right_y(value: float) -> None:
            self._sync_sbs_scroll(right, "scroll_target_y", value)

        def _sync_left_y(value: float) -> None:
            self._sync_sbs_scroll(left, "scroll_target_y", value)

        self.watch(left, "scroll_target_x", _sync_right_x, init=False)
        self.watch(right, "scroll_target_x", _sync_left_x, init=False)
        self.watch(left, "scroll_target_y", _sync_right_y, init=False)
        self.watch(right, "scroll_target_y", _sync_left_y, init=False)

    def set_editor_command(self, editor_command: str) -> None:
        self._editor_command = editor_command

    def set_pygments_style(self, style_name: str) -> None:
        """Pygments カラースタイルを設定する。空文字は内蔵 Dracula パレットを使用。"""
        self._pygments_style = style_name
        if style_name:
            built = _build_colors_from_pygments_style(style_name)
            self._syntax_colors = built if built else _SYNTAX_COLORS
        else:
            self._syntax_colors = _SYNTAX_COLORS

    def set_style_save_callback(self, callback: Any) -> None:
        """スタイル選択後に呼び出す保存コールバックを設定する。"""
        self._on_style_saved = callback

    # --- SBS スクロール同期 ---

    def _sync_sbs_scroll(self, target: DataTable, attr: str, value: float) -> None:
        """SBS モードで対向テーブルのスクロール位置を同期する。

        scroll_target_* を setattr するだけでは scroll_y（実描画位置）が更新されない。
        scroll_to(animate=False) を使うことで scroll_target と scroll_y を同時に設定する。
        値が既に一致する場合はループを防ぐため何もしない。
        """
        if self._diff_mode != DiffViewMode.SIDE_BY_SIDE:
            return
        if attr == "scroll_target_x":
            if target.scroll_target_x != value:
                target.scroll_to(x=value, animate=False)
        elif attr == "scroll_target_y":
            if target.scroll_target_y != value:
                target.scroll_to(y=value, animate=False)

    # --- メッセージハンドラ ---

    def on_show_overview(self, message: ShowOverview) -> None:
        self._current_mr_iid = message.mr_iid
        self._current_file_path = None
        self.run_worker(self._load_overview(message.mr_iid), exclusive=True)

    def on_show_diff(self, message: ShowDiff) -> None:
        self._current_mr_iid = message.mr_iid
        self._current_file_path = message.file_path
        self.run_worker(self._load_diff(message.mr_iid, message.file_path), exclusive=True)

    def on_comment_posted(self, message: CommentPosted) -> None:
        if self._current_mr_iid == message.mr_iid:
            if self._current_file_path:
                self.run_worker(
                    self._load_diff(message.mr_iid, self._current_file_path), exclusive=True
                )
            else:
                self.run_worker(self._load_overview(message.mr_iid), exclusive=True)

    def on_review_submitted(self, message: ReviewSubmitted) -> None:
        if self._current_mr_iid == message.mr_iid:
            if self._current_file_path:
                self.run_worker(
                    self._load_diff(message.mr_iid, self._current_file_path), exclusive=True
                )
            else:
                self.run_worker(self._load_overview(message.mr_iid), exclusive=True)

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        """選択行を更新し、SBS モードでは対向テーブルのカーソルを同期する。"""
        if self._view_state != ContentViewState.DIFF:
            return
        row_idx = event.cursor_row
        if 0 <= row_idx < len(self._diff_row_lines):
            new_n = self._diff_row_lines[row_idx]
            old_n = self._diff_row_old_lines.get(row_idx)
            if new_n is not None or old_n is not None:
                self._selected_line = new_n
                self._selected_old_line = old_n

        # フォーカスされているテーブルからのイベントのみ対向テーブルを同期する。
        # プログラムによる move_cursor が発する RowHighlighted は has_focus=False なので
        # ここに入らず、無限ループを防ぐ。
        if self._diff_mode == DiffViewMode.SIDE_BY_SIDE and event.data_table.has_focus:
            source = event.data_table
            try:
                left = self.query_one("#diff-table-left", DataTable)
                right = self.query_one("#diff-table-right", DataTable)
                other = right if source is left else left
                # scroll=False: スクロール同期は scroll_target_y の watch で行うため
                # ここで scroll_to_region を呼ぶと干渉してビューが跳ぶ
                other.move_cursor(row=row_idx, animate=False, scroll=False)
            except Exception as e:
                _logger.debug(f"Failed to sync cursor in SBS mode: {e}")

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """行選択 (Enter) 時の処理。
        - ギャップ行: コンテキスト展開または上下追加読み込み
        - コメント行: コメント閲覧ダイアログ表示
        """
        if self._view_state != ContentViewState.DIFF:
            return
        row_idx = event.cursor_row

        if row_idx in self._gap_row_ranges:
            start, end = self._gap_row_ranges[row_idx]
            action = self._gap_row_actions.get(row_idx, "all")
            if action == "top_load":
                self.run_worker(self._load_more_top(), exclusive=True)
            elif action == "bottom_load":
                self.run_worker(self._load_more_bottom(), exclusive=True)
            elif action == "above":
                self._expand_gap_above(start, end)
            elif action == "below":
                self._expand_gap_below(start, end)
            elif action == "inter_above":
                self.run_worker(self._load_inter_hunk_above(start, end), exclusive=False)
            elif action == "inter_below":
                self.run_worker(self._load_inter_hunk_below(start, end), exclusive=False)
            elif action == "inter_all":
                self.run_worker(self._load_inter_hunk_all(start, end), exclusive=False)
            else:
                self._expand_gap(row_idx)
            return

        if 0 <= row_idx < len(self._diff_row_lines):
            line_no = self._diff_row_lines[row_idx]
            if line_no is not None and line_no in self._comment_lines:
                self._show_comment_for_line(line_no)

    # --- ローダー ---

    async def _load_overview(self, mr_iid: int) -> None:
        self._view_state = ContentViewState.LOADING
        self.app.sub_title = f"Loading overview for !{mr_iid}..."
        self._show_log()
        log = self.query_one(RichLog)
        log.clear()
        try:
            mr_detail, discussions, drafts = await _gather_three(
                self._mr_service.get_mr_detail(mr_iid),
                self._comment_service.get_discussions(mr_iid),
                self._comment_service.get_draft_notes(mr_iid),
            )
            all_discussions = discussions + _drafts_as_discussions(drafts)
            text = _build_overview_text(mr_detail, all_discussions)
            log.clear()
            # scroll_end=False で末尾自動スクロールを抑制する。
            # write() は描画をリフレッシュまで遅延するため、先頭スクロールも
            # call_after_refresh で描画完了後に実行する。
            log.write(RichMarkdown(text), scroll_end=False)
            self._view_state = ContentViewState.OVERVIEW
            self.call_after_refresh(log.scroll_home, animate=False)
            log.focus()
        except GLReviewAPIError as exc:
            _logger.error("Failed to load overview for !%d: %s", mr_iid, exc.message)
            self._view_state = ContentViewState.ERROR
            await self.app.push_screen(ErrorDialog(exc.message))
        finally:
            self.app.sub_title = ""

    async def _load_diff(self, mr_iid: int, file_path: str) -> None:
        self._view_state = ContentViewState.LOADING
        self.app.sub_title = f"Loading diff for {file_path}..."
        self._show_diff_table()
        table = self.query_one("#diff-table", DataTable)
        table.clear(columns=True)
        self._diff_row_lines = []
        self._diff_row_old_lines = {}
        self._selected_line = None
        self._selected_old_line = None
        self._forced_ctx_indices = set()
        self._inter_hunk_loaded = {}
        self._file_content = []
        self._top_extra_count = 0
        self._bottom_extra_count = 0
        self._syntax_lexer = _get_lexer_for_path(file_path)
        try:
            file_diff, discussions, drafts = await _gather_three(
                self._mr_service.get_mr_diff(mr_iid, file_path),
                self._comment_service.get_discussions(mr_iid),
                self._comment_service.get_draft_notes(mr_iid),
            )
            all_discussions = discussions + _drafts_as_discussions(drafts)
            self._comment_lines = _get_comment_lines(all_discussions, file_path)
            self._discussions = all_discussions
            self._comment_map = _build_comment_map(all_discussions, file_path)
            self._current_diff_text = file_diff.diff
            self._full_parsed_diff = _parse_diff(file_diff.diff)
            self._first_diff_new_line, self._last_diff_new_line = _find_first_last_new_line(
                self._full_parsed_diff
            )
            self._render_diff()
            self._view_state = ContentViewState.DIFF
            if self._diff_mode == DiffViewMode.UNIFIED:
                table.focus()
            else:
                self.query_one("#diff-table-left", DataTable).focus()
        except GLReviewAPIError as exc:
            _logger.error("Failed to load diff for !%d %s: %s", mr_iid, file_path, exc.message)
            self._view_state = ContentViewState.ERROR
            await self.app.push_screen(ErrorDialog(exc.message))
        finally:
            self.app.sub_title = ""

    async def _fetch_file_content(self) -> None:
        """ファイル全体の内容を取得して _file_content にキャッシュする。"""
        if self._current_mr_iid is None or self._current_file_path is None:
            return
        try:
            lines = await self._mr_service.get_file_lines(
                self._current_mr_iid, self._current_file_path
            )
            self._file_content = lines
            _logger.debug(
                "Fetched file content: %s (%d lines)", self._current_file_path, len(lines)
            )
        except GLReviewAPIError as exc:
            _logger.warning("Failed to fetch file content: %s", exc.message)

    async def _load_more_top(self) -> None:
        """差分上部に 10 行追加読み込みして再描画する。"""
        if not self._file_content:
            await self._fetch_file_content()
        if not self._file_content:
            return
        self._top_extra_count += _LOAD_MORE_LINES
        self._render_diff()
        self._focus_diff_table()

    async def _load_more_bottom(self) -> None:
        """差分下部に 10 行追加読み込みして再描画する。"""
        if not self._file_content:
            await self._fetch_file_content()
        if not self._file_content:
            return
        self._bottom_extra_count += _LOAD_MORE_LINES
        self._render_diff()
        self._focus_diff_table()

    async def _load_inter_hunk_above(self, prev_end: int, next_start: int) -> None:
        """ハンク間ギャップの上側 _LOAD_MORE_LINES 行を読み込んで再描画する。"""
        if not self._file_content:
            await self._fetch_file_content()
        if not self._file_content:
            return
        key = (prev_end, next_start)
        above_count, below_count = self._inter_hunk_loaded.get(key, (0, 0))
        total_gap = next_start - prev_end - 1
        remaining = total_gap - above_count - below_count
        n = min(_LOAD_MORE_LINES, remaining)
        if n > 0:
            self._inter_hunk_loaded[key] = (above_count + n, below_count)
        self._render_diff()
        self._focus_diff_table()

    async def _load_inter_hunk_below(self, prev_end: int, next_start: int) -> None:
        """ハンク間ギャップの下側 _LOAD_MORE_LINES 行を読み込んで再描画する。"""
        if not self._file_content:
            await self._fetch_file_content()
        if not self._file_content:
            return
        key = (prev_end, next_start)
        above_count, below_count = self._inter_hunk_loaded.get(key, (0, 0))
        total_gap = next_start - prev_end - 1
        remaining = total_gap - above_count - below_count
        n = min(_LOAD_MORE_LINES, remaining)
        if n > 0:
            self._inter_hunk_loaded[key] = (above_count, below_count + n)
        self._render_diff()
        self._focus_diff_table()

    async def _load_inter_hunk_all(self, prev_end: int, next_start: int) -> None:
        """ハンク間ギャップの残り全行を読み込んで再描画する。"""
        if not self._file_content:
            await self._fetch_file_content()
        if not self._file_content:
            return
        key = (prev_end, next_start)
        above_count, below_count = self._inter_hunk_loaded.get(key, (0, 0))
        total_gap = next_start - prev_end - 1
        remaining = total_gap - above_count - below_count
        if remaining > 0:
            self._inter_hunk_loaded[key] = (above_count + remaining, below_count)
        self._render_diff()
        self._focus_diff_table()

    # --- 表示切替ヘルパー ---

    def _show_log(self) -> None:
        self.query_one("#empty-hint").display = False
        self.query_one(RichLog).display = True
        self.query_one("#unified-container").display = False
        self.query_one("#sbs-container").display = False

    def _show_diff_table(self) -> None:
        self.query_one("#empty-hint").display = False
        self.query_one(RichLog).display = False
        if self._diff_mode == DiffViewMode.UNIFIED:
            self.query_one("#unified-container").display = True
            self.query_one("#sbs-container").display = False
        else:
            self.query_one("#unified-container").display = False
            self.query_one("#sbs-container").display = True

    # --- 差分レンダラー ---

    def _add_inter_hunk_rows(
        self,
        rows: list[tuple[str, int | None, int | None, str]],
    ) -> list[tuple[str, int | None, int | None, str]]:
        """ハンクヘッダー間の省略行に読み込みエントリを挿入する。

        @@ ヘッダーを検出し、前のハンクの最終行番号と次のハンクの開始行番号の間に
        省略行がある場合、inter_above / inter_below / inter_all エントリを挿入する。
        エントリの old_n / new_n には prev_end / next_start（新ファイル行番号）を格納する。
        読み込み済みの行は ctx 行として展開して挿入する。
        """
        result: list[tuple[str, int | None, int | None, str]] = []
        last_new_no = 0  # 最後に確認した新ファイル行番号

        for entry in rows:
            t, _old_n, new_n, text = entry

            if t == "hunk":
                m = re.search(r"\+(\d+)", text)
                if m:
                    hunk_start = int(m.group(1))
                    if last_new_no > 0 and hunk_start > last_new_no + 1:
                        prev_end = last_new_no
                        next_start = hunk_start
                        key = (prev_end, next_start)
                        above_count, below_count = self._inter_hunk_loaded.get(key, (0, 0))
                        total_gap = next_start - prev_end - 1
                        above_count = min(above_count, total_gap)
                        below_count = min(below_count, total_gap - above_count)
                        remaining = total_gap - above_count - below_count

                        # 上側読み込み済み行を挿入
                        for i in range(above_count):
                            line_no = prev_end + 1 + i
                            if 1 <= line_no <= len(self._file_content):
                                result.append(
                                    (
                                        "ctx",
                                        line_no,
                                        line_no,
                                        " " + self._file_content[line_no - 1],
                                    )
                                )

                        # 省略行の読み込みエントリを挿入
                        if remaining > 0:
                            if remaining > _LOAD_MORE_LINES:
                                result.append(
                                    (
                                        "inter_above",
                                        prev_end,
                                        next_start,
                                        f"··· ↑ {_LOAD_MORE_LINES} lines above (Enter) ···",
                                    )
                                )
                                result.append(
                                    (
                                        "inter_below",
                                        prev_end,
                                        next_start,
                                        f"··· ↓ {_LOAD_MORE_LINES} lines below (Enter) ···",
                                    )
                                )
                            else:
                                result.append(
                                    (
                                        "inter_all",
                                        prev_end,
                                        next_start,
                                        f"··· {remaining} lines hidden (Enter to expand) ···",
                                    )
                                )

                        # 下側読み込み済み行を挿入（next_start に近い順）
                        for i in range(below_count - 1, -1, -1):
                            line_no = next_start - 1 - i
                            if 1 <= line_no <= len(self._file_content):
                                result.append(
                                    (
                                        "ctx",
                                        line_no,
                                        line_no,
                                        " " + self._file_content[line_no - 1],
                                    )
                                )

            # ctx/add 行のみ新ファイル行番号を更新する（gap などの擬似行番号は除外）
            if t in ("ctx", "add") and new_n is not None:
                last_new_no = new_n

            result.append(entry)

        return result

    def _build_augmented_rows(
        self,
    ) -> list[tuple[str, int | None, int | None, str]]:
        """上下追加行・context-filter 済み diff を結合したレンダリング用リストを返す。

        通常の gap エントリの old_n/new_n にはパースリスト内の開始・終了インデックスが入る。
        top_load/bottom_load エントリの old_n/new_n には各センチネル値を使用。
        """
        result: list[tuple[str, int | None, int | None, str]] = []

        # --- 先頭の追加読み込み行 ---
        if self._first_diff_new_line > 1:
            top_end_idx = self._first_diff_new_line - 1  # 0-indexed, exclusive
            if self._file_content and self._top_extra_count > 0:
                top_start_idx = max(0, top_end_idx - self._top_extra_count)
                if top_start_idx > 0:
                    result.append(
                        (
                            "top_load",
                            _TOP_LOAD_SENTINEL[0],
                            _TOP_LOAD_SENTINEL[1],
                            f"··· load {_LOAD_MORE_LINES} more lines above (Enter) ···",
                        )
                    )
                for i in range(top_start_idx, top_end_idx):
                    result.append(("ctx", i + 1, i + 1, " " + self._file_content[i]))
            else:
                result.append(
                    (
                        "top_load",
                        _TOP_LOAD_SENTINEL[0],
                        _TOP_LOAD_SENTINEL[1],
                        f"··· load {_LOAD_MORE_LINES} more lines above (Enter) ···",
                    )
                )

        # --- 通常の diff 行（context フィルタ済み + ハンク間ギャップ挿入） ---
        filtered = _apply_context_filter(
            self._full_parsed_diff, _CONTEXT_LINES, self._forced_ctx_indices
        )
        result.extend(self._add_inter_hunk_rows(filtered))

        # --- 末尾の追加読み込み行 ---
        if self._last_diff_new_line > 0:
            bottom_start_idx = self._last_diff_new_line  # 0-indexed
            if self._file_content:
                bottom_end_idx = min(
                    bottom_start_idx + self._bottom_extra_count, len(self._file_content)
                )
                for i in range(bottom_start_idx, bottom_end_idx):
                    result.append(("ctx", i + 1, i + 1, " " + self._file_content[i]))
                has_more = bottom_end_idx < len(self._file_content)
            else:
                has_more = True  # ファイル未取得 → まだあると仮定

            if has_more:
                result.append(
                    (
                        "bottom_load",
                        _BOTTOM_LOAD_SENTINEL[0],
                        _BOTTOM_LOAD_SENTINEL[1],
                        f"··· load {_LOAD_MORE_LINES} more lines below (Enter) ···",
                    )
                )

        return result

    def _row_for_line(self, line_no: int) -> int | None:
        """新ファイル行番号に最も近いテーブル行インデックスを返す。"""
        best_row: int | None = None
        best_dist = float("inf")
        for row_idx, ln in enumerate(self._diff_row_lines):
            if ln is None:
                continue
            dist = abs(ln - line_no)
            if dist < best_dist:
                best_dist = dist
                best_row = row_idx
        return best_row

    def _focus_diff_table(self) -> None:
        """現在の差分モードに応じてテーブルにフォーカスし、カーソルを直前の選択行に復元する。"""
        target_row: int | None = None
        if self._selected_line is not None:
            target_row = self._row_for_line(self._selected_line)

        if self._diff_mode == DiffViewMode.UNIFIED:
            table = self.query_one("#diff-table", DataTable)
            table.focus()
            if target_row is not None:
                table.move_cursor(row=target_row, animate=False)
        else:
            left = self.query_one("#diff-table-left", DataTable)
            right = self.query_one("#diff-table-right", DataTable)
            left.focus()
            if target_row is not None:
                # 両テーブルを直接移動する。
                # right は has_focus=False なので on_data_table_row_highlighted が
                # 呼ばれても同期ループにはならない。
                left.move_cursor(row=target_row, animate=False, scroll=False)
                right.move_cursor(row=target_row, animate=False, scroll=False)

    def _compute_overflow_comment_markers(
        self,
        rows: list[tuple[str, int | None, int | None, str]],
    ) -> set[int]:
        """diff に表示されていないコメント行を末尾のコード行に割り当てる。

        表示範囲外のコメント行（行番号が diff の可視範囲を超えている等）について、
        末尾のコード行から逆順に 💬 マークを割り当てる。

        Returns:
            💬 を追加表示すべき rows リストのインデックス集合。
        """
        if not self._comment_lines:
            return set()

        # diff に実際に表示されている行番号を収集
        visible_lines: set[int] = set()
        code_row_positions: list[int] = []  # add/rem/ctx 行の rows インデックス

        for i, (t, old_n, new_n, _) in enumerate(rows):
            if t in ("add", "ctx"):
                if new_n is not None:
                    visible_lines.add(new_n)
                code_row_positions.append(i)
            elif t == "rem":
                if old_n is not None:
                    visible_lines.add(old_n)
                code_row_positions.append(i)

        # 表示されていないコメント行
        overflow = [line for line in sorted(self._comment_lines) if line not in visible_lines]
        if not overflow:
            return set()

        # 末尾のコード行から逆順に割り当て（複数ある場合は順に上にずらす）
        result: set[int] = set()
        for i in range(min(len(overflow), len(code_row_positions))):
            result.add(code_row_positions[-(i + 1)])
        return result

    def _render_diff(self) -> None:
        """現在の状態で差分を DataTable にレンダリングする（ネットワークアクセスなし）。"""
        self._diff_row_lines = []
        self._diff_row_old_lines = {}
        self._gap_row_ranges = {}
        self._gap_row_actions = {}
        self._diff_row_types = []
        rows = self._build_augmented_rows()
        overflow_markers = self._compute_overflow_comment_markers(rows)

        table = self.query_one("#diff-table", DataTable)
        table.clear(columns=True)

        if self._diff_mode == DiffViewMode.UNIFIED:
            table.add_column("Old", key="old_no", width=5)
            table.add_column("New", key="new_no", width=_LINE_NO_WIDTH)
            table.add_column("Content", key="content")
            if self._wrap_lines:
                # Old(5+2) + New(6+2) + Content padding(2) + scrollbar(1) = 18
                self._code_wrap_width = max(40, table.size.width - 18)
            self._render_unified_table(table, rows, overflow_markers)
            self._update_gutter(rows, "diff-gutter")
        else:
            left = self.query_one("#diff-table-left", DataTable)
            right = self.query_one("#diff-table-right", DataTable)
            left.clear(columns=True)
            right.clear(columns=True)
            left.add_column("Old#", key="old_no", width=_LINE_NO_WIDTH)
            left.add_column("Old", key="old_content")
            right.add_column("New#", key="new_no", width=_LINE_NO_WIDTH)
            right.add_column("New", key="new_content")
            if self._wrap_lines:
                # LineNo(6+2) + Content padding(2) + scrollbar(1) = 11
                self._code_wrap_width = max(40, left.size.width - 11)
            self._render_sbs_tables(left, right, rows, overflow_markers)
            self._update_gutter(rows, "diff-gutter-sbs")

    def _update_gutter(
        self, rows: list[tuple[str, int | None, int | None, str]], gutter_id: str
    ) -> None:
        """差分行リストからガターのマークを更新する。"""
        mark_types = [t if t in ("add", "rem", "hunk") else "" for t, *_ in rows]
        self.query_one(f"#{gutter_id}", DiffGutter).set_rows(mark_types)

    def _content_cell(self, text: str, style: str = "") -> Text:
        """折り返しモードに応じてコンテンツセル用 Text を返す。"""
        if self._wrap_lines:
            text = _wrap_text(text, self._code_wrap_width)
            return Text(text, style=style)
        return Text(text, style=style, no_wrap=True)

    def _get_token_color(self, token_type: Any) -> str | None:
        """インスタンスのカラーマップからトークンの Rich スタイル文字列を返す。"""
        t = token_type
        while t is not None:
            color = self._syntax_colors.get(t)
            if color is not None:
                return color
            parent = t.parent
            if parent is t:
                break
            t = parent
        return None

    def _lex_lines(self, lines: list[str]) -> list[list[tuple[Any, str]]]:
        """複数のコード行を一括 lex し、行ごとのトークンリストを返す。

        pygments が Vue SFC 等の複数行コンテキストを必要とする場合に
        正しくハイライトできるよう、全行を連結して 1 度だけ lex する。
        """
        if self._syntax_lexer is None or not lines:
            return [[] for _ in lines]

        full_code = "\n".join(lines)
        per_line: list[list[tuple[Any, str]]] = []
        current: list[tuple[Any, str]] = []

        for token_type, value in _pygments_lex(full_code, self._syntax_lexer):
            parts = value.split("\n")
            for i, part in enumerate(parts):
                if i > 0:
                    per_line.append(current)
                    current = []
                if part:
                    current.append((token_type, part))
        per_line.append(current)

        # 行数を lines に合わせる（念のため）
        while len(per_line) < len(lines):
            per_line.append([])

        return per_line[: len(lines)]

    def _code_cell(
        self,
        text: str,
        bg_style: str = "",
        has_diff_prefix: bool = False,
        precomputed_tokens: list[tuple[Any, str]] | None = None,
    ) -> Text:
        """シンタックスハイライト付きコードセルを返す。

        レキサーが未設定の場合は _content_cell にフォールバックする。
        has_diff_prefix=True のとき、先頭の +/-/space をプレフィックスとして扱い
        それ以降の文字列をハイライト対象にする。
        precomputed_tokens が指定された場合は再 lex せずそのトークンを使用する。
        """
        if self._syntax_lexer is None:
            return self._content_cell(text, bg_style)

        prefix_char = ""
        code = text
        if has_diff_prefix and text:
            prefix_char = text[0]
            code = text[1:]

        tokens: Any = (
            precomputed_tokens
            if precomputed_tokens is not None
            else _pygments_lex(code, self._syntax_lexer)
        )

        result = Text(no_wrap=not self._wrap_lines)
        if prefix_char:
            result.append(prefix_char, style=bg_style)

        if self._wrap_lines:
            # precomputed_tokens を再 lex せず使うことで多行ハイライトコンテキストを保持する。
            # カラム位置を追跡して折り返し位置に \n を挿入する。
            code_width = self._code_wrap_width
            col = 1 if prefix_char else 0
            for token_type, value in tokens:
                if not value or value == "\n":
                    continue
                fg = self._get_token_color(token_type)
                if fg and bg_style:
                    style = f"{fg} {bg_style}"
                elif fg:
                    style = fg
                else:
                    style = bg_style or ""
                while col + len(value) > code_width:
                    space = code_width - col
                    if space > 0:
                        result.append(value[:space], style=style)
                        value = value[space:]
                    result.append("\n")
                    col = 0
                result.append(value, style=style)
                col += len(value)
        else:
            for token_type, value in tokens:
                if not value:
                    continue
                fg = self._get_token_color(token_type)
                if fg and bg_style:
                    style = f"{fg} {bg_style}"
                elif fg:
                    style = fg
                else:
                    style = bg_style or ""
                result.append(value, style=style)

        return result

    def _row_height(self) -> int | None:
        """折り返しモード時は None（自動検出）、通常は 1 を返す。"""
        return None if self._wrap_lines else 1

    def _render_unified_table(
        self,
        table: DataTable,
        rows: list[tuple[str, int | None, int | None, str]],
        overflow_markers: set[int],
    ) -> None:
        """unified diff の行リストを DataTable に描画する。"""
        row_idx = 0
        row_height = self._row_height()

        # 全コード行を一括 lex（Vue SFC 等の複数行コンテキストに対応）
        code_lines = [
            text[1:] if text else "" for t, _, _, text in rows if t in ("add", "rem", "ctx")
        ]
        precomputed = self._lex_lines(code_lines)
        code_row_idx = 0

        for rows_pos, (t, old_n, new_n, text) in enumerate(rows):
            has_overflow = rows_pos in overflow_markers
            if t in ("gap", "top_load", "bottom_load", "inter_above", "inter_below", "inter_all"):
                gap_size = (
                    (new_n - old_n + 1)
                    if (t == "gap" and old_n is not None and new_n is not None)
                    else 0
                )
                if t == "inter_above":
                    self._gap_row_ranges[row_idx] = (old_n, new_n)  # type: ignore[arg-type]
                    self._gap_row_actions[row_idx] = "inter_above"
                    table.add_row(
                        Text("↑", style=_DIFF_GAP_STYLE),
                        Text("↑", style=_DIFF_GAP_STYLE),
                        self._content_cell(text, _DIFF_GAP_STYLE),
                        key=f"gap_{row_idx}",
                        height=1,
                    )
                    self._diff_row_lines.append(None)
                    self._diff_row_types.append("gap")
                elif t == "inter_below":
                    self._gap_row_ranges[row_idx] = (old_n, new_n)  # type: ignore[arg-type]
                    self._gap_row_actions[row_idx] = "inter_below"
                    table.add_row(
                        Text("↓", style=_DIFF_GAP_STYLE),
                        Text("↓", style=_DIFF_GAP_STYLE),
                        self._content_cell(text, _DIFF_GAP_STYLE),
                        key=f"gap_{row_idx}",
                        height=1,
                    )
                    self._diff_row_lines.append(None)
                    self._diff_row_types.append("gap")
                elif t == "inter_all":
                    self._gap_row_ranges[row_idx] = (old_n, new_n)  # type: ignore[arg-type]
                    self._gap_row_actions[row_idx] = "inter_all"
                    table.add_row(
                        Text("···", style=_DIFF_GAP_STYLE),
                        Text("···", style=_DIFF_GAP_STYLE),
                        self._content_cell(text, _DIFF_GAP_STYLE),
                        key=f"gap_{row_idx}",
                        height=1,
                    )
                    self._diff_row_lines.append(None)
                    self._diff_row_types.append("gap")
                elif t == "top_load":
                    self._gap_row_ranges[row_idx] = (old_n, new_n)  # type: ignore[arg-type]
                    self._gap_row_actions[row_idx] = "top_load"
                    table.add_row(
                        Text("···", style=_DIFF_GAP_STYLE),
                        Text("···", style=_DIFF_GAP_STYLE),
                        self._content_cell(text, _DIFF_GAP_STYLE),
                        key=f"gap_{row_idx}",
                        height=1,
                    )
                    self._diff_row_lines.append(None)
                    self._diff_row_types.append("gap")
                elif t == "bottom_load":
                    self._gap_row_ranges[row_idx] = (old_n, new_n)  # type: ignore[arg-type]
                    self._gap_row_actions[row_idx] = "bottom_load"
                    table.add_row(
                        Text("···", style=_DIFF_GAP_STYLE),
                        Text("···", style=_DIFF_GAP_STYLE),
                        self._content_cell(text, _DIFF_GAP_STYLE),
                        key=f"gap_{row_idx}",
                        height=1,
                    )
                    self._diff_row_lines.append(None)
                    self._diff_row_types.append("gap")
                elif gap_size > _LOAD_MORE_LINES:
                    # 大きいギャップ → 上側・下側の2行に分割
                    above_text = f"··· ↑ {_LOAD_MORE_LINES} lines above (Enter) ···"
                    below_text = f"··· ↓ {_LOAD_MORE_LINES} lines below (Enter) ···"
                    self._gap_row_ranges[row_idx] = (old_n, new_n)  # type: ignore[arg-type]
                    self._gap_row_actions[row_idx] = "above"
                    table.add_row(
                        Text("↑", style=_DIFF_GAP_STYLE),
                        Text("↑", style=_DIFF_GAP_STYLE),
                        self._content_cell(above_text, _DIFF_GAP_STYLE),
                        key=f"gap_{row_idx}",
                        height=1,
                    )
                    self._diff_row_lines.append(None)
                    self._diff_row_types.append("gap")
                    row_idx += 1
                    self._gap_row_ranges[row_idx] = (old_n, new_n)  # type: ignore[arg-type]
                    self._gap_row_actions[row_idx] = "below"
                    table.add_row(
                        Text("↓", style=_DIFF_GAP_STYLE),
                        Text("↓", style=_DIFF_GAP_STYLE),
                        self._content_cell(below_text, _DIFF_GAP_STYLE),
                        key=f"gap_{row_idx}",
                        height=1,
                    )
                    self._diff_row_lines.append(None)
                    self._diff_row_types.append("gap")
                else:
                    # 小さいギャップ → 全展開1行
                    self._gap_row_ranges[row_idx] = (old_n, new_n)  # type: ignore[arg-type]
                    self._gap_row_actions[row_idx] = "all"
                    table.add_row(
                        Text("···", style=_DIFF_GAP_STYLE),
                        Text("···", style=_DIFF_GAP_STYLE),
                        self._content_cell(text, _DIFF_GAP_STYLE),
                        key=f"gap_{row_idx}",
                        height=1,
                    )
                    self._diff_row_lines.append(None)
                    self._diff_row_types.append("gap")
            elif t in ("hunk", "header"):
                # @@ ハンクヘッダーとファイルヘッダーは表示しない（行番号で代替可能）
                continue
            elif t == "add":
                tokens = precomputed[code_row_idx]
                code_row_idx += 1
                no_label = (
                    f"{new_n}💬" if (new_n in self._comment_lines or has_overflow) else str(new_n)
                )
                table.add_row(
                    Text("", style=_DIFF_ADD_STYLE),
                    Text(no_label, style=_DIFF_ADD_STYLE),
                    self._code_cell(
                        text, _DIFF_ADD_STYLE, has_diff_prefix=True, precomputed_tokens=tokens
                    ),
                    key=f"add_{row_idx}",
                    height=row_height,
                )
                self._diff_row_lines.append(new_n)
                self._diff_row_types.append("add")
            elif t == "rem":
                tokens = precomputed[code_row_idx]
                code_row_idx += 1
                no_label = (
                    f"{old_n}💬" if (old_n in self._comment_lines or has_overflow) else str(old_n)
                )
                table.add_row(
                    Text(no_label, style=_DIFF_REM_STYLE),
                    Text("", style=_DIFF_REM_STYLE),
                    self._code_cell(
                        text, _DIFF_REM_STYLE, has_diff_prefix=True, precomputed_tokens=tokens
                    ),
                    key=f"rem_{row_idx}",
                    height=row_height,
                )
                self._diff_row_lines.append(None)
                self._diff_row_types.append("rem")
                if old_n is not None:
                    self._diff_row_old_lines[row_idx] = old_n
            else:  # ctx
                tokens = precomputed[code_row_idx]
                code_row_idx += 1
                no_label = (
                    f"{new_n}💬"
                    if (new_n in self._comment_lines or has_overflow)
                    else (str(new_n) if new_n is not None else "")
                )
                table.add_row(
                    str(old_n) if old_n is not None else "",
                    no_label,
                    self._code_cell(text, has_diff_prefix=True, precomputed_tokens=tokens),
                    key=f"ctx_{row_idx}",
                    height=row_height,
                )
                self._diff_row_lines.append(new_n)
                self._diff_row_types.append("ctx")
                if old_n is not None:
                    self._diff_row_old_lines[row_idx] = old_n
            row_idx += 1

    def _render_sbs_tables(
        self,
        left: DataTable,
        right: DataTable,
        rows: list[tuple[str, int | None, int | None, str]],
        overflow_markers: set[int],
    ) -> None:
        """side-by-side の左右テーブルを同時に描画する。"""
        row_idx = 0
        row_height = self._row_height()

        # 全コード行を一括 lex（Vue SFC 等の複数行コンテキストに対応）
        code_lines = [
            (text[1:] if text.startswith("-") else text)
            if t == "rem"
            else (text[1:] if text.startswith("+") else text)
            if t == "add"
            else (text[1:] if text.startswith(" ") else text)
            for t, _, _, text in rows
            if t in ("rem", "add", "ctx")
        ]
        precomputed = self._lex_lines(code_lines)
        code_row_idx = 0

        # pending タプル: (line_no, text, tokens, has_overflow)
        pending_rem: list[tuple[int | None, str, list[tuple[Any, str]], bool]] = []
        pending_add: list[tuple[int | None, str, list[tuple[Any, str]], bool]] = []

        def _flush() -> None:
            nonlocal row_idx
            if not pending_rem and not pending_add:
                return
            max_len = max(len(pending_rem), len(pending_add))
            for k in range(max_len):
                old_n2, old_t, old_tok, old_ov = (
                    pending_rem[k] if k < len(pending_rem) else (None, "", [], False)
                )
                new_n2, new_t, new_tok, new_ov = (
                    pending_add[k] if k < len(pending_add) else (None, "", [], False)
                )
                left_no = (
                    f"{old_n2}💬"
                    if old_n2 and (old_n2 in self._comment_lines or old_ov)
                    else (str(old_n2) if old_n2 else "")
                )
                right_no = (
                    f"{new_n2}💬"
                    if new_n2 and (new_n2 in self._comment_lines or new_ov)
                    else (str(new_n2) if new_n2 else "")
                )
                left.add_row(
                    Text(left_no, style=_DIFF_REM_STYLE if old_t else ""),
                    self._code_cell(
                        old_t,
                        _DIFF_REM_STYLE if old_t else "",
                        precomputed_tokens=old_tok if old_t else None,
                    ),
                    key=f"sbs_l_{row_idx}",
                    height=row_height,
                )
                right.add_row(
                    Text(right_no, style=_DIFF_ADD_STYLE if new_t else ""),
                    self._code_cell(
                        new_t,
                        _DIFF_ADD_STYLE if new_t else "",
                        precomputed_tokens=new_tok if new_t else None,
                    ),
                    key=f"sbs_r_{row_idx}",
                    height=row_height,
                )
                self._diff_row_lines.append(new_n2)
                if old_n2 is not None:
                    self._diff_row_old_lines[row_idx] = old_n2
                if old_n2 is not None and new_n2 is None:
                    self._diff_row_types.append("rem")
                elif new_n2 is not None and old_n2 is None:
                    self._diff_row_types.append("add")
                elif old_n2 is not None and new_n2 is not None:
                    self._diff_row_types.append("rem")
                else:
                    self._diff_row_types.append("ctx")
                row_idx += 1
            pending_rem.clear()
            pending_add.clear()

        for rows_pos, (t, old_n, new_n, text) in enumerate(rows):
            has_overflow = rows_pos in overflow_markers
            if t == "rem":
                stripped = text[1:] if text.startswith("-") else text
                pending_rem.append((old_n, stripped, precomputed[code_row_idx], has_overflow))
                code_row_idx += 1
            elif t == "add":
                stripped = text[1:] if text.startswith("+") else text
                pending_add.append((new_n, stripped, precomputed[code_row_idx], has_overflow))
                code_row_idx += 1
            else:
                _flush()
                if t in (
                    "gap",
                    "top_load",
                    "bottom_load",
                    "inter_above",
                    "inter_below",
                    "inter_all",
                ):
                    gap_size = (
                        (new_n - old_n + 1)
                        if (t == "gap" and old_n is not None and new_n is not None)
                        else 0
                    )
                    if t == "inter_above":
                        self._gap_row_ranges[row_idx] = (old_n, new_n)  # type: ignore[arg-type]
                        self._gap_row_actions[row_idx] = "inter_above"
                        left.add_row(
                            Text("↑", style=_DIFF_GAP_STYLE),
                            self._content_cell(text, _DIFF_GAP_STYLE),
                            key=f"gap_l_{row_idx}",
                            height=1,
                        )
                        right.add_row(
                            Text("↑", style=_DIFF_GAP_STYLE),
                            self._content_cell(text, _DIFF_GAP_STYLE),
                            key=f"gap_r_{row_idx}",
                            height=1,
                        )
                        self._diff_row_lines.append(None)
                        self._diff_row_types.append("gap")
                    elif t == "inter_below":
                        self._gap_row_ranges[row_idx] = (old_n, new_n)  # type: ignore[arg-type]
                        self._gap_row_actions[row_idx] = "inter_below"
                        left.add_row(
                            Text("↓", style=_DIFF_GAP_STYLE),
                            self._content_cell(text, _DIFF_GAP_STYLE),
                            key=f"gap_l_{row_idx}",
                            height=1,
                        )
                        right.add_row(
                            Text("↓", style=_DIFF_GAP_STYLE),
                            self._content_cell(text, _DIFF_GAP_STYLE),
                            key=f"gap_r_{row_idx}",
                            height=1,
                        )
                        self._diff_row_lines.append(None)
                        self._diff_row_types.append("gap")
                    elif t == "inter_all":
                        self._gap_row_ranges[row_idx] = (old_n, new_n)  # type: ignore[arg-type]
                        self._gap_row_actions[row_idx] = "inter_all"
                        left.add_row(
                            Text("···", style=_DIFF_GAP_STYLE),
                            self._content_cell(text, _DIFF_GAP_STYLE),
                            key=f"gap_l_{row_idx}",
                            height=1,
                        )
                        right.add_row(
                            Text("···", style=_DIFF_GAP_STYLE),
                            self._content_cell(text, _DIFF_GAP_STYLE),
                            key=f"gap_r_{row_idx}",
                            height=1,
                        )
                        self._diff_row_lines.append(None)
                        self._diff_row_types.append("gap")
                    elif t == "top_load":
                        self._gap_row_ranges[row_idx] = (old_n, new_n)  # type: ignore[arg-type]
                        self._gap_row_actions[row_idx] = "top_load"
                        left.add_row(
                            Text("···", style=_DIFF_GAP_STYLE),
                            self._content_cell(text, _DIFF_GAP_STYLE),
                            key=f"gap_l_{row_idx}",
                            height=1,
                        )
                        right.add_row(
                            Text("···", style=_DIFF_GAP_STYLE),
                            self._content_cell(text, _DIFF_GAP_STYLE),
                            key=f"gap_r_{row_idx}",
                            height=1,
                        )
                        self._diff_row_lines.append(None)
                        self._diff_row_types.append("gap")
                    elif t == "bottom_load":
                        self._gap_row_ranges[row_idx] = (old_n, new_n)  # type: ignore[arg-type]
                        self._gap_row_actions[row_idx] = "bottom_load"
                        left.add_row(
                            Text("···", style=_DIFF_GAP_STYLE),
                            self._content_cell(text, _DIFF_GAP_STYLE),
                            key=f"gap_l_{row_idx}",
                            height=1,
                        )
                        right.add_row(
                            Text("···", style=_DIFF_GAP_STYLE),
                            self._content_cell(text, _DIFF_GAP_STYLE),
                            key=f"gap_r_{row_idx}",
                            height=1,
                        )
                        self._diff_row_lines.append(None)
                        self._diff_row_types.append("gap")
                    elif gap_size > _LOAD_MORE_LINES:
                        # 大きいギャップ → 上側・下側の2行に分割
                        above_text = f"··· ↑ {_LOAD_MORE_LINES} lines above (Enter) ···"
                        below_text = f"··· ↓ {_LOAD_MORE_LINES} lines below (Enter) ···"
                        self._gap_row_ranges[row_idx] = (old_n, new_n)  # type: ignore[arg-type]
                        self._gap_row_actions[row_idx] = "above"
                        left.add_row(
                            Text("↑", style=_DIFF_GAP_STYLE),
                            self._content_cell(above_text, _DIFF_GAP_STYLE),
                            key=f"gap_l_{row_idx}",
                            height=1,
                        )
                        right.add_row(
                            Text("↑", style=_DIFF_GAP_STYLE),
                            self._content_cell(above_text, _DIFF_GAP_STYLE),
                            key=f"gap_r_{row_idx}",
                            height=1,
                        )
                        self._diff_row_lines.append(None)
                        self._diff_row_types.append("gap")
                        row_idx += 1
                        self._gap_row_ranges[row_idx] = (old_n, new_n)  # type: ignore[arg-type]
                        self._gap_row_actions[row_idx] = "below"
                        left.add_row(
                            Text("↓", style=_DIFF_GAP_STYLE),
                            self._content_cell(below_text, _DIFF_GAP_STYLE),
                            key=f"gap_l_{row_idx}",
                            height=1,
                        )
                        right.add_row(
                            Text("↓", style=_DIFF_GAP_STYLE),
                            self._content_cell(below_text, _DIFF_GAP_STYLE),
                            key=f"gap_r_{row_idx}",
                            height=1,
                        )
                        self._diff_row_lines.append(None)
                        self._diff_row_types.append("gap")
                    else:
                        # 小さいギャップ → 全展開1行
                        self._gap_row_ranges[row_idx] = (old_n, new_n)  # type: ignore[arg-type]
                        self._gap_row_actions[row_idx] = "all"
                        left.add_row(
                            Text("···", style=_DIFF_GAP_STYLE),
                            self._content_cell(text, _DIFF_GAP_STYLE),
                            key=f"gap_l_{row_idx}",
                            height=1,
                        )
                        right.add_row(
                            Text("···", style=_DIFF_GAP_STYLE),
                            self._content_cell(text, _DIFF_GAP_STYLE),
                            key=f"gap_r_{row_idx}",
                            height=1,
                        )
                        self._diff_row_lines.append(None)
                        self._diff_row_types.append("gap")
                elif t in ("hunk", "header"):
                    # @@ ハンクヘッダーとファイルヘッダーは表示しない
                    continue
                else:  # ctx
                    ctx_text = text[1:] if text.startswith(" ") else text
                    ctx_tokens = precomputed[code_row_idx]
                    code_row_idx += 1
                    right_no = (
                        f"{new_n}💬"
                        if new_n is not None and (new_n in self._comment_lines or has_overflow)
                        else (str(new_n) if new_n is not None else "")
                    )
                    left.add_row(
                        str(old_n) if old_n is not None else "",
                        self._code_cell(ctx_text, precomputed_tokens=ctx_tokens),
                        key=f"ctx_l_{row_idx}",
                        height=row_height,
                    )
                    right.add_row(
                        right_no,
                        self._code_cell(ctx_text, precomputed_tokens=ctx_tokens),
                        key=f"ctx_r_{row_idx}",
                        height=row_height,
                    )
                    self._diff_row_lines.append(new_n)
                    self._diff_row_types.append("ctx")
                    if old_n is not None:
                        self._diff_row_old_lines[row_idx] = old_n
                row_idx += 1

        _flush()

    # --- ギャップ展開・コメント閲覧 ---

    def _expand_gap(self, row_idx: int) -> None:
        """選択されたギャップ行のコンテキストを全て展開して再描画する。"""
        start, end = self._gap_row_ranges[row_idx]
        for i in range(start, end + 1):
            self._forced_ctx_indices.add(i)
        self._render_diff()
        self._focus_diff_table()

    def _expand_gap_above(self, start: int, end: int) -> None:
        """ギャップの上側 _LOAD_MORE_LINES 行を展開して再描画する。"""
        limit = min(start + _LOAD_MORE_LINES, end + 1)
        for i in range(start, limit):
            self._forced_ctx_indices.add(i)
        self._render_diff()
        self._focus_diff_table()

    def _expand_gap_below(self, start: int, end: int) -> None:
        """ギャップの下側 _LOAD_MORE_LINES 行を展開して再描画する。"""
        limit = max(end - _LOAD_MORE_LINES, start - 1)
        for i in range(end, limit, -1):
            self._forced_ctx_indices.add(i)
        self._render_diff()
        self._focus_diff_table()

    def _show_comment_for_line(self, line_no: int) -> None:
        """指定行のコメント閲覧ダイアログを表示する。"""
        discs = self._comment_map.get(line_no, [])
        if discs:
            self.app.push_screen(CommentViewDialog(discs, line_no, self._current_file_path or ""))

    # --- クエリ ---

    def get_current_file_path(self) -> str | None:
        """diff 表示中のファイルパス（リポジトリルートからの相対パス）を返す。"""
        if self._view_state == ContentViewState.DIFF:
            return self._current_file_path
        return None

    def get_selected_line(self) -> tuple[str, int] | None:
        """現在選択中の (file_path, line_number) を返す。行未選択時は行1を使用。"""
        if self._view_state == ContentViewState.DIFF and self._current_file_path is not None:
            return (self._current_file_path, self._selected_line or 1)
        return None

    # --- アクション ---

    def action_toggle_diff_mode(self) -> None:
        if self._view_state != ContentViewState.DIFF:
            return
        self._diff_mode = (
            DiffViewMode.SIDE_BY_SIDE
            if self._diff_mode == DiffViewMode.UNIFIED
            else DiffViewMode.UNIFIED
        )
        if self._current_mr_iid is not None and self._current_file_path is not None:
            self.run_worker(
                self._load_diff(self._current_mr_iid, self._current_file_path),
                exclusive=True,
            )

    def action_toggle_wrap(self) -> None:
        """差分表示の折り返しモードを切り替える。"""
        if self._view_state != ContentViewState.DIFF:
            return
        self._wrap_lines = not self._wrap_lines
        if self._current_diff_text:
            self._render_diff()
            if self._diff_mode == DiffViewMode.UNIFIED:
                self.query_one("#diff-table", DataTable).focus()
            else:
                self.query_one("#diff-table-left", DataTable).focus()

    async def action_expand_all_lines(self) -> None:
        """差分の全行を展開して表示する（ギャップ・上下追加行・ハンク間行をすべて読み込む）。"""
        if self._view_state != ContentViewState.DIFF:
            return
        if not self._file_content:
            await self._fetch_file_content()
        if not self._file_content:
            return

        # ① ハンク内コンテキストギャップをすべて展開
        for i, (t, *_) in enumerate(self._full_parsed_diff):
            if t == "ctx":
                self._forced_ctx_indices.add(i)

        # ② 先頭の追加行をすべて表示
        self._top_extra_count = max(self._first_diff_new_line - 1, 0)

        # ③ 末尾の追加行をすべて表示
        self._bottom_extra_count = max(len(self._file_content) - self._last_diff_new_line, 0)

        # ④ ハンク間ギャップをすべて読み込む
        last_new_no = 0
        for t, _, new_n, text in self._full_parsed_diff:
            if t == "hunk":
                m = re.search(r"\+(\d+)", text)
                if m:
                    hunk_start = int(m.group(1))
                    if last_new_no > 0 and hunk_start > last_new_no + 1:
                        prev_end = last_new_no
                        next_start = hunk_start
                        key = (prev_end, next_start)
                        total_gap = next_start - prev_end - 1
                        self._inter_hunk_loaded[key] = (total_gap, 0)
            if t in ("ctx", "add") and new_n is not None:
                last_new_no = new_n

        self._render_diff()
        self._focus_diff_table()

    async def action_select_syntax(self) -> None:
        """シンタックスハイライト言語選択ダイアログを開く。"""
        if self._view_state != ContentViewState.DIFF:
            return
        current_name: str | None = None
        if self._syntax_lexer is not None:
            current_name = getattr(self._syntax_lexer, "name", None)

        async def _on_select(alias: str | None) -> None:
            if alias is None:
                # キャンセル — 何も変えない
                self._focus_diff_table()
                return
            if alias == _SYNTAX_AUTO:
                self._syntax_lexer = _get_lexer_for_path(self._current_file_path)
            elif alias == _SYNTAX_NONE:
                self._syntax_lexer = None
            else:
                from pygments.lexers import get_lexer_by_name
                from pygments.util import ClassNotFound

                try:
                    self._syntax_lexer = get_lexer_by_name(alias, stripnl=True)
                except ClassNotFound:
                    _logger.warning("Unknown syntax alias: %s", alias)
                    self._focus_diff_table()
                    return
            if self._current_diff_text:
                self._render_diff()
            self._focus_diff_table()

        await self.app.push_screen(SyntaxSelectDialog(current_name), _on_select)

    async def action_select_style(self) -> None:
        """Pygments カラースタイル選択ダイアログを開く。"""
        if self._view_state not in (ContentViewState.DIFF, ContentViewState.OVERVIEW):
            return

        async def _on_style_select(style_id: str | None) -> None:
            if style_id is None:
                # キャンセル
                if self._view_state == ContentViewState.DIFF:
                    self._focus_diff_table()
                return
            if style_id == _STYLE_DEFAULT:
                self.set_pygments_style("")
            else:
                self.set_pygments_style(style_id)
            # コンフィグに保存
            if self._on_style_saved is not None:
                self._on_style_saved(self._pygments_style)
            # 再描画
            if self._view_state == ContentViewState.DIFF and self._current_diff_text:
                self._render_diff()
                self._focus_diff_table()

        await self.app.push_screen(StyleSelectDialog(self._pygments_style), _on_style_select)

    def _focused_diff_table(self) -> DataTable | None:
        """現在フォーカスされている差分テーブルを返す。SBS では実際にフォーカスを持つ側を返す。"""
        if self._view_state != ContentViewState.DIFF:
            return None
        if self._diff_mode == DiffViewMode.UNIFIED:
            return self.query_one("#diff-table", DataTable)
        right = self.query_one("#diff-table-right", DataTable)
        if right.has_focus:
            return right
        return self.query_one("#diff-table-left", DataTable)

    def action_diff_cursor_down(self) -> None:
        """差分表示でカーソルを1行下に移動する。"""
        if self._view_state == ContentViewState.OVERVIEW:
            self.query_one(RichLog).scroll_down(animate=False)
            return
        table = self._focused_diff_table()
        if table is not None:
            table.action_cursor_down()

    def action_diff_cursor_up(self) -> None:
        """差分表示でカーソルを1行上に移動する。"""
        if self._view_state == ContentViewState.OVERVIEW:
            self.query_one(RichLog).scroll_up(animate=False)
            return
        table = self._focused_diff_table()
        if table is not None:
            table.action_cursor_up()

    def action_diff_scroll_left(self) -> None:
        """差分表示を左にスクロールする。"""
        if self._view_state == ContentViewState.OVERVIEW:
            self.query_one(RichLog).scroll_left(animate=False)
            return
        if self._view_state != ContentViewState.DIFF:
            return
        if self._diff_mode == DiffViewMode.UNIFIED:
            self.query_one("#diff-table", DataTable).scroll_left(animate=False)
        else:
            self.query_one("#diff-table-left", DataTable).scroll_left(animate=False)
            self.query_one("#diff-table-right", DataTable).scroll_left(animate=False)

    def action_diff_scroll_right(self) -> None:
        """差分表示を右にスクロールする。"""
        if self._view_state == ContentViewState.OVERVIEW:
            self.query_one(RichLog).scroll_right(animate=False)
            return
        if self._view_state != ContentViewState.DIFF:
            return
        if self._diff_mode == DiffViewMode.UNIFIED:
            self.query_one("#diff-table", DataTable).scroll_right(animate=False)
        else:
            self.query_one("#diff-table-left", DataTable).scroll_right(animate=False)
            self.query_one("#diff-table-right", DataTable).scroll_right(animate=False)

    def action_jump_next_diff_line(self) -> None:
        """次の変更行 (add/rem) へカーソルを移動する。"""
        if self._view_state != ContentViewState.DIFF:
            return
        table = self._focused_diff_table()
        if table is None:
            return
        current = table.cursor_row
        for i in range(current + 1, len(self._diff_row_types)):
            if self._diff_row_types[i] in ("add", "rem"):
                table.move_cursor(row=i, animate=False)
                return

    def action_jump_prev_diff_line(self) -> None:
        """前の変更行 (add/rem) へカーソルを移動する。"""
        if self._view_state != ContentViewState.DIFF:
            return
        table = self._focused_diff_table()
        if table is None:
            return
        current = table.cursor_row
        for i in range(current - 1, -1, -1):
            if self._diff_row_types[i] in ("add", "rem"):
                table.move_cursor(row=i, animate=False)
                return

    async def action_add_comment(self) -> None:
        if self._view_state == ContentViewState.DIFF:
            if self._current_mr_iid is None or self._current_file_path is None:
                return
            new_line = self._selected_line
            old_line = self._selected_old_line
            if new_line is not None and old_line is not None:
                # ctx (unchanged) line: both sides required by GitLab API
                line = new_line
                line_type = "new"
            elif new_line is not None:
                # add line
                line = new_line
                line_type = "new"
                old_line = None
            elif old_line is not None:
                # rem line
                line = old_line
                line_type = "old"
                old_line = None
            else:
                line = 1
                line_type = "new"
                old_line = None
            context = CommentContext(
                mr_iid=self._current_mr_iid,
                comment_type=CommentType.INLINE,
                file_path=self._current_file_path,
                line=line,
                line_type=line_type,
                old_line=old_line,
            )
        elif self._view_state == ContentViewState.OVERVIEW:
            if self._current_mr_iid is None:
                return
            context = CommentContext(
                mr_iid=self._current_mr_iid,
                comment_type=CommentType.NOTE,
            )
        else:
            return

        await self.app.push_screen(
            CommentDialog(context, self._comment_service, self._editor_command)
        )

    async def action_submit_review(self) -> None:
        """現在のMRの下書きコメントを一括公開する(レビュー送信)。"""
        if self._current_mr_iid is None:
            return
        mr_iid = self._current_mr_iid
        try:
            drafts = await self._comment_service.get_draft_notes(mr_iid)
        except GLReviewAPIError as exc:
            await self.app.push_screen(ErrorDialog(exc.message))
            return

        if not drafts:
            self.app.notify("No draft comments to submit.")
            return

        await self.app.push_screen(SubmitReviewDialog(mr_iid, drafts, self._comment_service))

    async def clear_content(self) -> None:
        """コンテンツをクリアして初期状態に戻す。"""
        self._view_state = ContentViewState.EMPTY
        self._current_mr_iid = None
        self._current_file_path = None
        self._selected_line = None
        self._selected_old_line = None
        self._diff_row_lines = []
        self._diff_row_old_lines = {}
        self._diff_row_types = []
        self._discussions = []
        self._comment_map = {}
        self._current_diff_text = ""
        self._full_parsed_diff = []
        self._forced_ctx_indices = set()
        self._gap_row_ranges = {}
        self._gap_row_actions = {}
        self._inter_hunk_loaded = {}
        self._syntax_lexer = None
        self._file_content = []
        self._top_extra_count = 0
        self._bottom_extra_count = 0
        self._first_diff_new_line = 0
        self._last_diff_new_line = 0
        log = self.query_one(RichLog)
        log.clear()
        log.display = False
        self.query_one("#diff-table", DataTable).clear(columns=True)
        self.query_one("#unified-container").display = False
        self.query_one("#diff-table-left", DataTable).clear(columns=True)
        self.query_one("#diff-table-right", DataTable).clear(columns=True)
        self.query_one("#sbs-container").display = False
        self.query_one("#empty-hint").display = True


async def _gather_two(coro1, coro2):
    """2つのコルーチンを並行実行して結果のタプルを返す。"""
    import asyncio

    result1, result2 = await asyncio.gather(coro1, coro2)
    return result1, result2


async def _gather_three(coro1, coro2, coro3):
    """3つのコルーチンを並行実行して結果のタプルを返す。"""
    import asyncio

    result1, result2, result3 = await asyncio.gather(coro1, coro2, coro3)
    return result1, result2, result3
