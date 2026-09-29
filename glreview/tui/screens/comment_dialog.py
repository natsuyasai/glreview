"""CommentDialog — コメント入力モーダルダイアログ。"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, TextArea

from glreview.infrastructure.logger import get_logger
from glreview.models import CommentContext, CommentType
from glreview.services import CommentService
from glreview.services.exceptions import EmptyCommentError, GLReviewAPIError
from glreview.tui.messages import CommentPosted
from glreview.tui.screens.error_dialog import ErrorDialog

_logger = get_logger(__name__)


class CommentDialog(ModalScreen[None]):
    """コメント入力ダイアログ。INLINE / NOTE / REPLY の3種別に対応。

    送信すると即座には公開されず、GitLabのDraft Notes APIで下書きとして
    レビューに追加される(ブラウザの「レビューを開始」「レビューに追加」相当)。
    実際に他のメンバーに見えるようにするには、レビュー送信操作で公開する必要がある。
    """

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("ctrl+s", "submit", "Add to Review"),
        Binding("ctrl+e", "open_editor", "External Editor"),
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(
        self,
        comment_context: CommentContext,
        comment_service: CommentService,
        editor_command: str,
    ) -> None:
        super().__init__()
        self._comment_context = comment_context
        self._comment_service = comment_service
        self._editor_command = editor_command
        self._submitting = False

    def on_mount(self) -> None:
        self.query_one(TextArea).focus()

    def compose(self) -> ComposeResult:
        title, subtitle = self._build_header()
        with Vertical(id="dialog-container"):
            yield Label(title, id="comment-title")
            if subtitle:
                yield Label(subtitle, id="comment-subtitle")
            yield TextArea(id="comment-input")
            yield Label("", id="comment-error")
            with Horizontal(id="comment-buttons"):
                yield Button("Add to Review (Ctrl+S)", variant="primary", id="submit-button")
                yield Button("Cancel (Esc)", variant="default", id="cancel-button")

    def _build_header(self) -> tuple[str, str]:
        ctx = self._comment_context
        if ctx.comment_type == CommentType.INLINE:
            return (
                "[bold]Add Inline Comment to Review (Draft)[/bold]",
                f"{ctx.file_path} (line {ctx.line})",
            )
        if ctx.comment_type == CommentType.NOTE:
            return "[bold]Add Note to Review (Draft)[/bold]", "MR-level comment"
        return "[bold]Reply to Discussion (Draft)[/bold]", ""

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "submit-button":
            self.run_action("submit")
        elif event.button.id == "cancel-button":
            self.action_cancel()

    async def action_submit(self) -> None:
        if self._submitting:
            return
        text = self.query_one(TextArea).text.strip()
        if not text:
            self.query_one("#comment-error", Label).update("[red]Comment cannot be empty.[/red]")
            return

        self._submitting = True
        error_label = self.query_one("#comment-error", Label)
        error_label.update("")

        try:
            ctx = self._comment_context
            if ctx.comment_type == CommentType.INLINE:
                await self._comment_service.add_inline_comment(
                    mr_iid=ctx.mr_iid,
                    file_path=ctx.file_path,  # type: ignore[arg-type]
                    line=ctx.line,  # type: ignore[arg-type]
                    body=text,
                    line_type=ctx.line_type or "new",
                    old_line=ctx.old_line,
                )
            elif ctx.comment_type == CommentType.NOTE:
                await self._comment_service.add_note(mr_iid=ctx.mr_iid, body=text)
            else:
                await self._comment_service.reply_to_discussion(
                    mr_iid=ctx.mr_iid,
                    discussion_id=ctx.discussion_id,  # type: ignore[arg-type]
                    body=text,
                )
            _logger.info("Draft comment added to review for MR !%d", ctx.mr_iid)
            self.post_message(CommentPosted(ctx.mr_iid))
            self.dismiss()
        except EmptyCommentError:
            error_label.update("[red]Comment cannot be empty.[/red]")
        except GLReviewAPIError as exc:
            _logger.error("Failed to post comment: %s", exc.message)
            await self.app.push_screen(ErrorDialog(exc.message))
        finally:
            self._submitting = False

    async def action_open_editor(self) -> None:
        """外部エディタでコメントを入力する。"""
        text_area = self.query_one(TextArea)
        current_text = text_area.text
        tmp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                suffix=".md",
                delete=False,
                encoding="utf-8",
            ) as tmp:
                tmp.write(current_text)
                tmp_path = Path(tmp.name)

            editor_cmd = self._editor_command or "vi"
            _logger.info("Opening external editor: %s %s", editor_cmd, tmp_path)

            with self.app.suspend():
                result = subprocess.run(  # noqa: S603
                    [editor_cmd, str(tmp_path)],
                    check=False,
                )

            if result.returncode != 0:
                _logger.warning("Editor exited with code %d", result.returncode)

            new_text = tmp_path.read_text(encoding="utf-8")
            text_area.load_text(new_text)
        except FileNotFoundError:
            await self.app.push_screen(ErrorDialog(f"Editor not found: {self._editor_command}"))
        except Exception as exc:
            _logger.error("External editor error: %s", exc)
            await self.app.push_screen(ErrorDialog(f"Editor error: {exc}"))
        finally:
            if tmp_path is not None and tmp_path.exists():
                tmp_path.unlink()

    def action_cancel(self) -> None:
        self.dismiss()
