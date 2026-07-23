"""CommentViewDialog — インラインコメント閲覧モーダルダイアログ。"""

from __future__ import annotations

from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, RichLog

from glreview.models import Discussion


class CommentViewDialog(ModalScreen[None]):
    """指定行のコメント（ディスカッション）を表示するモーダルダイアログ。"""

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("escape", "dismiss", "Close"),
        Binding("q", "dismiss", "Close"),
    ]

    def __init__(
        self,
        discussions: list[Discussion],
        line_no: int,
        file_path: str,
    ) -> None:
        super().__init__()
        self._discussions = discussions
        self._line_no = line_no
        self._file_path = file_path

    def compose(self) -> ComposeResult:
        with Vertical(id="comment-view-container"):
            yield Label("[bold]💬 Comments[/bold]", id="comment-view-title")
            yield Label(f"{self._file_path}:{self._line_no}", id="comment-view-subtitle")
            yield RichLog(id="comment-view-log", markup=True, highlight=False)
            yield Button("Close (Esc / q)", variant="default", id="close-button")

    def on_mount(self) -> None:
        log = self.query_one(RichLog)
        for disc in self._discussions:
            for i, note in enumerate(disc.notes):
                indent = "  " if i > 0 else ""
                draft_tag = "[yellow][DRAFT][/yellow] " if note.is_draft else ""
                log.write(f"{indent}{draft_tag}[bold]{note.author}[/bold] ({note.created_at})")
                for body_line in note.body.splitlines():
                    log.write(f"{indent}  {body_line}")
            log.write("")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "close-button":
            self.dismiss()

    def action_dismiss(self) -> None:
        self.dismiss()
