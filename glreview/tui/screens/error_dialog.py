"""ErrorDialog — エラーメッセージ表示モーダル。"""

from __future__ import annotations

from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label


class ErrorDialog(ModalScreen[None]):
    """エラーメッセージを表示するモーダルダイアログ。"""

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("escape", "dismiss", "Close"),
        Binding("enter", "dismiss", "Close"),
    ]

    def __init__(self, error_message: str) -> None:
        super().__init__()
        self._error_message = error_message

    def compose(self) -> ComposeResult:
        with Vertical(id="error-container"):
            yield Label(f"[bold red]Error[/bold red]\n\n{self._error_message}", id="error-message")
            yield Button("OK", variant="error", id="ok-button")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "ok-button":
            self.dismiss()

    def action_dismiss(self) -> None:
        self.dismiss()
