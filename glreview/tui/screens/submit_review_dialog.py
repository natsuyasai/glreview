"""SubmitReviewDialog — 下書きコメント一括公開(レビュー送信)確認モーダルダイアログ。"""

from __future__ import annotations

from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, RichLog

from glreview.infrastructure.logger import get_logger
from glreview.models import Note
from glreview.services import CommentService
from glreview.services.exceptions import GLReviewAPIError
from glreview.tui.messages import ReviewSubmitted

_logger = get_logger(__name__)


class SubmitReviewDialog(ModalScreen[None]):
    """下書きコメント一覧を表示し、レビュー送信(Draft Notes の一括公開)を確認するダイアログ。"""

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("ctrl+s", "submit", "Submit Review"),
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(
        self,
        mr_iid: int,
        drafts: list[Note],
        comment_service: CommentService,
    ) -> None:
        super().__init__()
        self._mr_iid = mr_iid
        self._drafts = drafts
        self._comment_service = comment_service
        self._submitting = False

    def compose(self) -> ComposeResult:
        with Vertical(id="submit-review-container"):
            yield Label(
                f"[bold]Submit Review[/bold] — {len(self._drafts)} draft comment(s)",
                id="submit-review-title",
            )
            yield RichLog(id="submit-review-log", markup=True, highlight=False)
            yield Label("", id="submit-review-error")
            with Horizontal(id="submit-review-buttons"):
                yield Button("Submit Review (Ctrl+S)", variant="primary", id="submit-button")
                yield Button("Cancel (Esc)", variant="default", id="cancel-button")

    def on_mount(self) -> None:
        log = self.query_one(RichLog)
        if not self._drafts:
            log.write("[dim](No draft comments)[/dim]")
        for note in self._drafts:
            location = ""
            if note.position is not None:
                line_no = note.position.new_line or note.position.old_line
                location = f" [{note.position.file_path}:{line_no}]"
            log.write(f"[bold]{note.author}[/bold]{location}")
            for body_line in note.body.splitlines():
                log.write(f"  {body_line}")
            log.write("")

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "submit-button":
            await self.run_action("submit")
        elif event.button.id == "cancel-button":
            self.action_cancel()

    async def action_submit(self) -> None:
        if self._submitting:
            return
        self._submitting = True
        error_label = self.query_one("#submit-review-error", Label)
        error_label.update("")

        try:
            await self._comment_service.publish_review(self._mr_iid)
            _logger.info(
                "Review submitted for MR !%d (%d draft comments)",
                self._mr_iid,
                len(self._drafts),
            )
            self.post_message(ReviewSubmitted(self._mr_iid))
            self.dismiss()
        except GLReviewAPIError as exc:
            _logger.error("Failed to submit review: %s", exc.message)
            error_label.update(f"[red]{exc.message}[/red]")
        finally:
            self._submitting = False

    def action_cancel(self) -> None:
        self.dismiss()
