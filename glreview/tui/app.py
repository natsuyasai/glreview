"""GLReviewApp — TUI Application メインアプリクラス。"""

from __future__ import annotations

import asyncio
import os
import shlex
import shutil
import subprocess
from pathlib import Path
from typing import ClassVar

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import Footer, Header, Tree

from glreview.infrastructure.config import ConfigManager
from glreview.infrastructure.git_detector import GitRepoDetector
from glreview.infrastructure.logger import get_logger
from glreview.models import AppConfig
from glreview.services import CommentService, GitLabClient, MRService
from glreview.services.exceptions import GLReviewAPIError
from glreview.tui.messages import CommentPosted, ReviewSubmitted, ShowDiff, ShowOverview
from glreview.tui.screens.error_dialog import ErrorDialog
from glreview.tui.screens.help_screen import HelpScreen
from glreview.tui.screens.settings_screen import SettingsScreen
from glreview.tui.widgets.content_panel import ContentPanel
from glreview.tui.widgets.mr_list_panel import MRListPanel

_logger = get_logger(__name__)

_CSS_PATH = Path(__file__).parent / "styles.tcss"

# ターミナルエミュレータの候補: (コマンド名, エディタコマンドの前に置く追加引数)
# Windows 用候補（検出順）
_TERMINAL_CANDIDATES_WIN: list[tuple[str, list[str]]] = [
    ("wt", ["-w", "0", "new-tab", "--", "cmd", "/k"]),  # Windows Terminal
    ("pwsh", ["-NoExit", "-Command"]),  # PowerShell 7+
    ("powershell", ["-NoExit", "-Command"]),  # Windows PowerShell
]

# Unix/Linux/macOS 用候補
_TERMINAL_CANDIDATES: list[tuple[str, list[str]]] = [
    ("xterm", ["-e"]),
    ("x-terminal-emulator", ["-e"]),
    ("konsole", ["-e"]),
    ("alacritty", ["-e"]),
    ("kitty", []),
    ("wezterm", ["start", "--"]),
    ("gnome-terminal", ["--"]),
]

# Windows の cmd.exe シェル組み込みコマンド（shutil.which で見つからないもの）
_WIN_SHELL_BUILTINS = {"start"}


def _resolve_terminal_cmd(terminal_cfg: str) -> list[str] | None:
    """ターミナル起動コマンドをリストとして返す。検出できなければ None。

    Args:
        terminal_cfg: 設定値 (例: "xterm -e")。空文字の場合は自動検出。

    Returns:
        エディタコマンドの直前に置くコマンドリスト。例: ["xterm", "-e"]
    """
    if terminal_cfg:
        parts = shlex.split(terminal_cfg)
        if not parts:
            return None
        # Windows: "start" は cmd.exe の組み込みコマンドのため shutil.which では見つからない。
        # "cmd /c start ..." に変換して実行する。
        is_windows = os.name == "nt"
        if is_windows and parts[0].lower() in _WIN_SHELL_BUILTINS:
            return ["cmd", "/c", *parts]
        if shutil.which(parts[0]):
            return parts
        return None

    is_windows = os.name == "nt"
    if is_windows:
        # Windows: 既知のターミナルエミュレータを順に試す
        for name, extra_args in _TERMINAL_CANDIDATES_WIN:
            if shutil.which(name):
                return [name, *extra_args]
        # フォールバック: cmd /c start で新しい cmd ウィンドウを開く
        return ["cmd", "/c", "start", "cmd", "/k"]
    else:
        # 環境変数 $TERMINAL を確認（"-e" スタイルと仮定）
        env_val = os.environ.get("TERMINAL", "").strip()
        if env_val:
            name = shlex.split(env_val)[0]
            if shutil.which(name):
                return [name, "-e"]

        # 一般的なターミナルエミュレータを順に試す
        for name, extra_args in _TERMINAL_CANDIDATES:
            if shutil.which(name):
                return [name, *extra_args]

        return None


class GLReviewApp(App):
    """GitLab MR ブラウザ・コメント TUI アプリケーション。"""

    CSS_PATH = _CSS_PATH

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("q", "quit", "Quit"),
        Binding("question_mark", "show_help", "Help"),
        Binding("r", "refresh", "Refresh"),
        Binding("m", "focus_mr_list", "Focus MR"),
        Binding("e", "open_in_editor", "Editor", priority=True),
        Binding("backslash", "toggle_sidebar", "Toggle Sidebar"),
        Binding("b", "checkout_branch", "Checkout Branch"),
        Binding("comma", "show_settings", "Settings"),
    ]

    def __init__(
        self,
        config: AppConfig,
        config_manager: ConfigManager | None = None,
        initial_mr_id: int | None = None,
        cwd: Path | None = None,
    ) -> None:
        super().__init__()
        self._config = config
        self._config_manager = config_manager
        self._initial_mr_id = initial_mr_id
        self._cwd = cwd
        self._git_root: Path = cwd if cwd is not None else Path.cwd()
        self._sidebar_visible = True
        self._client: GitLabClient | None = None
        self._mr_service: MRService | None = None
        self._comment_service: CommentService | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        # ウィジェットは on_mount で初期化後に置き換えるため、
        # プレースホルダーとして空の状態でマウントする
        with Horizontal(id="main-container"):
            pass
        yield Footer()

    async def on_mount(self) -> None:
        """アプリ起動時にGitLabへ接続し、ウィジェットを初期化する。"""
        self.title = "glreview"
        self.sub_title = "Connecting..."

        try:
            detector = GitRepoDetector(cwd=self._cwd)
            project_info = detector.detect(self._config)
            project_path = project_info.project_path

            # git リポジトリルートを確定（エディタ起動時のフルパス解決に使用）
            try:
                git_root_result = subprocess.run(
                    ["git", "rev-parse", "--show-toplevel"],  # noqa: S607
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    timeout=10,
                    shell=False,
                    cwd=str(self._cwd) if self._cwd else None,
                )
                if git_root_result.returncode == 0:
                    self._git_root = Path(git_root_result.stdout.strip())
            except Exception:
                _logger.debug("Failed to determine git root; using default", exc_info=True)

            self._client = GitLabClient(self._config)
            await self._client.connect()

            self._mr_service = MRService(self._client, project_path)
            await self._mr_service.load()

            self._comment_service = CommentService(self._client, project_path)
            await self._comment_service.load()

        except GLReviewAPIError as exc:
            _logger.error("Connection failed: %s", exc.message)
            self.sub_title = "Connection failed"
            await self.push_screen(ErrorDialog(exc.message))
            return
        except Exception as exc:
            _logger.exception("Unexpected error during startup")
            self.sub_title = "Startup error"
            await self.push_screen(ErrorDialog(str(exc)))
            return

        self.sub_title = ""

        # main-container 内のウィジェットを正しく生成・マウントする
        container = self.query_one("#main-container")
        # ダミーウィジェットを削除して再生成
        for child in list(container.children):
            await child.remove()

        mr_panel = MRListPanel(self._mr_service, self._comment_service)
        content_panel = ContentPanel(self._mr_service, self._comment_service)
        content_panel.set_editor_command(self._config.editor)
        if self._config.pygments_style:
            content_panel.set_pygments_style(self._config.pygments_style)
        if self._config_manager is not None:
            config_manager = self._config_manager

            def _save_style(style_name: str) -> None:
                config_manager.save_setting("appearance", "pygments_style", style_name)

            content_panel.set_style_save_callback(_save_style)

        await container.mount(mr_panel, content_panel)

        # 初期MR IDが指定されている場合は後で展開する
        if self._initial_mr_id is not None:
            _logger.info("Auto-expanding MR !%d", self._initial_mr_id)

    # --- アクション ---

    async def action_show_help(self) -> None:
        await self.push_screen(HelpScreen())

    async def action_show_settings(self) -> None:
        """設定画面を開く。"""
        if self._config_manager is None:
            return

        async def _open_config_in_editor(path: Path) -> None:
            terminal_prefix = _resolve_terminal_cmd(self._config.terminal)
            if terminal_prefix is None:
                await self.push_screen(
                    ErrorDialog(
                        "ターミナルエミュレータが見つかりません。\n"
                        "設定の terminal にコマンドを指定してください。"
                    )
                )
                return
            editor = self._config.editor or "vi"
            try:
                subprocess.Popen([*terminal_prefix, editor, str(path)])  # noqa: S603
            except Exception as exc:
                await self.push_screen(ErrorDialog(f"エディタ起動エラー: {exc}"))

        await self.push_screen(
            SettingsScreen(self._config, self._config_manager, _open_config_in_editor)
        )

    async def action_refresh(self) -> None:
        if self._mr_service is None or self._comment_service is None:
            return
        self._mr_service.invalidate_cache()
        self._comment_service.invalidate_cache()

        try:
            mr_panel = self.query_one(MRListPanel)
            await mr_panel.refresh_list()
        except Exception:  # noqa: S110
            pass

        try:
            content_panel = self.query_one(ContentPanel)
            await content_panel.clear_content()
        except Exception:  # noqa: S110
            pass

        _logger.info("Refreshed MR list and cleared cache")

    async def action_open_in_editor(self) -> None:
        """現在表示中のファイルを別ターミナルの外部エディタで開く。"""
        try:
            content_panel = self.query_one(ContentPanel)
            rel_path = content_panel.get_current_file_path()
        except Exception:
            return

        if rel_path is None:
            return

        full_path = self._git_root / rel_path
        editor = self._config.editor or "vi"
        terminal_prefix = _resolve_terminal_cmd(self._config.terminal)

        if terminal_prefix is None:
            await self.push_screen(
                ErrorDialog(
                    "ターミナルエミュレータが見つかりません。\n"
                    "config.toml の [editor] セクションに terminal を設定してください。\n\n"
                    '例: terminal = "xterm -e"'
                )
            )
            return

        cmd = [*terminal_prefix, editor, str(full_path)]
        _logger.info("Opening editor in terminal: %s", cmd)
        try:
            subprocess.Popen(cmd)  # noqa: S603
        except FileNotFoundError as exc:
            await self.push_screen(ErrorDialog(f"コマンドが見つかりません: {exc}"))
        except Exception as exc:
            _logger.error("Editor terminal error: %s", exc)
            await self.push_screen(ErrorDialog(f"エディタ起動エラー: {exc}"))

    def action_toggle_sidebar(self) -> None:
        self._sidebar_visible = not self._sidebar_visible
        try:
            mr_panel = self.query_one(MRListPanel)
            if self._sidebar_visible:
                mr_panel.remove_class("-hidden")
            else:
                mr_panel.add_class("-hidden")
        except Exception:  # noqa: S110
            pass

    def action_focus_mr_list(self) -> None:
        try:
            mr_panel = self.query_one(MRListPanel)
            tree = mr_panel.query_one(Tree)
            tree.focus()
        except Exception:  # noqa: S110
            pass

    # --- メッセージハンドラ（兄弟ウィジェット間のルーティング） ---

    def on_show_overview(self, message: ShowOverview) -> None:
        """MRListPanel から上がってきた ShowOverview を ContentPanel に転送する。"""
        message.stop()
        try:
            content_panel = self.query_one(ContentPanel)
            content_panel.on_show_overview(message)
        except Exception:  # noqa: S110
            pass

    def on_show_diff(self, message: ShowDiff) -> None:
        """MRListPanel から上がってきた ShowDiff を ContentPanel に転送する。"""
        message.stop()
        try:
            content_panel = self.query_one(ContentPanel)
            content_panel.on_show_diff(message)
        except Exception:  # noqa: S110
            pass

    def on_comment_posted(self, message: CommentPosted) -> None:
        """CommentDialog から上がってきた CommentPosted を ContentPanel に転送する。"""
        message.stop()
        try:
            content_panel = self.query_one(ContentPanel)
            content_panel.on_comment_posted(message)
        except Exception:  # noqa: S110
            pass

    def on_review_submitted(self, message: ReviewSubmitted) -> None:
        """SubmitReviewDialog から上がってきた ReviewSubmitted を ContentPanel に転送する。"""
        message.stop()
        try:
            content_panel = self.query_one(ContentPanel)
            content_panel.on_review_submitted(message)
        except Exception:  # noqa: S110
            pass

    async def action_checkout_branch(self) -> None:
        """選択中の MR のソースブランチをチェックアウトまたはスイッチする。"""
        if self._mr_service is None:
            return
        try:
            mr_panel = self.query_one(MRListPanel)
        except Exception:
            return
        mr_iid = mr_panel.get_selected_mr_iid()
        if mr_iid is None:
            return
        self.run_worker(self._checkout_branch_worker(mr_iid), exclusive=False)

    async def _checkout_branch_worker(self, mr_iid: int) -> None:
        """ブランチのチェックアウト処理を非同期ワーカーとして実行する。"""
        from glreview.infrastructure.git_ops import GitOpsError, checkout_or_switch_branch

        self.sub_title = f"MR !{mr_iid} の情報を取得中..."
        try:
            assert self._mr_service is not None
            detail = await self._mr_service.get_mr_detail(mr_iid)
        except Exception as exc:
            self.sub_title = ""
            await self.push_screen(ErrorDialog(f"MR 情報の取得に失敗しました: {exc}"))
            return

        source_branch = detail.source_branch
        if not source_branch:
            self.sub_title = ""
            await self.push_screen(ErrorDialog("ソースブランチ情報が取得できませんでした。"))
            return

        remote = self._config.remote_name or "origin"
        self.sub_title = f"'{source_branch}' をチェックアウト中..."
        try:
            result = await asyncio.to_thread(
                checkout_or_switch_branch, source_branch, remote, self._cwd
            )
            self.notify(result.message)
        except GitOpsError as exc:
            await self.push_screen(ErrorDialog(str(exc)))
        except Exception as exc:
            _logger.exception("Unexpected error during git checkout")
            await self.push_screen(ErrorDialog(f"予期しないエラー: {exc}"))
        finally:
            self.sub_title = ""

    def action_quit(self) -> None:
        self.exit()
