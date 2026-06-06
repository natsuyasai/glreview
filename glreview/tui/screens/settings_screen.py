"""SettingsScreen — config.toml 設定画面モーダル。"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Input, Label, Switch

from glreview.infrastructure.config import ConfigManager
from glreview.models import AppConfig


class SettingsScreen(ModalScreen[None]):
    """config.toml の設定を編集するモーダルスクリーン。

    Ctrl+S で保存、Ctrl+E で外部エディタ起動、Esc で閉じる。
    """

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("escape", "dismiss", "閉じる"),
        Binding("ctrl+s", "save", "保存", priority=True),
        Binding("ctrl+e", "open_in_editor", "エディタで開く", priority=True),
    ]

    # (section, toml_key, widget_id): Input フィールド定義
    _STR_FIELDS: ClassVar[list[tuple[str, str, str]]] = [
        ("gitlab", "url", "input-gitlab-url"),
        ("auth", "token", "input-auth-token"),
        ("editor", "command", "input-editor-command"),
        ("editor", "terminal", "input-editor-terminal"),
        ("logging", "level", "input-logging-level"),
        ("appearance", "theme", "input-appearance-theme"),
        ("appearance", "pygments_style", "input-appearance-pygments"),
        ("git", "remote_name", "input-git-remote"),
    ]

    def __init__(
        self,
        config: AppConfig,
        config_manager: ConfigManager,
        open_in_editor: Callable[[Path], Awaitable[None]],
    ) -> None:
        super().__init__()
        self._config = config
        self._config_manager = config_manager
        self._open_in_editor = open_in_editor

    def compose(self) -> ComposeResult:
        with Vertical(id="settings-container"):
            yield Label("[bold]設定[/bold]", id="settings-title")
            yield Label(str(self._config_manager.config_path), id="settings-path")
            with VerticalScroll(id="settings-form"):
                yield Label("[bold]\\[gitlab][/bold]", classes="settings-section-header")
                with Horizontal(classes="settings-row"):
                    yield Label("URL", classes="settings-label")
                    yield Input(self._config.gitlab_url, id="input-gitlab-url")
                with Horizontal(classes="settings-row"):
                    yield Label("SSL Verify", classes="settings-label")
                    yield Switch(self._config.ssl_verify, id="switch-ssl-verify")

                yield Label("[bold]\\[auth][/bold]", classes="settings-section-header")
                with Horizontal(classes="settings-row"):
                    yield Label("Token", classes="settings-label")
                    yield Input(self._config.token, password=True, id="input-auth-token")

                yield Label("[bold]\\[editor][/bold]", classes="settings-section-header")
                with Horizontal(classes="settings-row"):
                    yield Label("Command", classes="settings-label")
                    yield Input(self._config.editor, id="input-editor-command")
                with Horizontal(classes="settings-row"):
                    yield Label("Terminal", classes="settings-label")
                    yield Input(
                        self._config.terminal,
                        placeholder="空=自動検出",
                        id="input-editor-terminal",
                    )

                yield Label("[bold]\\[logging][/bold]", classes="settings-section-header")
                with Horizontal(classes="settings-row"):
                    yield Label("Level", classes="settings-label")
                    yield Input(self._config.log_level, id="input-logging-level")

                yield Label("[bold]\\[appearance][/bold]", classes="settings-section-header")
                with Horizontal(classes="settings-row"):
                    yield Label("Theme", classes="settings-label")
                    yield Input(self._config.theme, id="input-appearance-theme")
                with Horizontal(classes="settings-row"):
                    yield Label("Pygments Style", classes="settings-label")
                    yield Input(
                        self._config.pygments_style,
                        placeholder="空=内蔵テーマ",
                        id="input-appearance-pygments",
                    )

                yield Label("[bold]\\[git][/bold]", classes="settings-section-header")
                with Horizontal(classes="settings-row"):
                    yield Label("Remote Name", classes="settings-label")
                    yield Input(
                        self._config.remote_name,
                        placeholder="空=origin",
                        id="input-git-remote",
                    )
            yield Label(
                "Ctrl+S: 保存  Ctrl+E: エディタで開く  Esc: 閉じる",
                id="settings-hint",
            )

    def on_mount(self) -> None:
        self.query_one("#input-gitlab-url", Input).focus()

    def action_save(self) -> None:
        """全フィールドの値を config.toml に書き込む。"""
        try:
            for section, key, widget_id in self._STR_FIELDS:
                value = self.query_one(f"#{widget_id}", Input).value
                self._config_manager.save_setting(section, key, value)
            ssl_verify: bool = self.query_one("#switch-ssl-verify", Switch).value
            self._config_manager.save_setting("gitlab", "ssl_verify", ssl_verify)
            self.app.notify(
                "設定を保存しました。変更の一部は再起動後に反映されます。",
                severity="information",
            )
        except Exception as exc:
            self.app.notify(f"保存エラー: {exc}", severity="error")

    async def action_open_in_editor(self) -> None:
        """config.toml を外部エディタで開く。"""
        await self._open_in_editor(self._config_manager.config_path)
