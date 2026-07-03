"""HelpScreen — キーバインド一覧表示モーダル。"""

from __future__ import annotations

from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import DataTable, Label

_KEYBINDINGS: list[tuple[str, str, str]] = [
    # (category, key, action)
    ("Global", "q", "Quit"),
    ("Global", "?", "Toggle Help"),
    ("Global", ",", "Settings"),
    ("Global", "r", "Refresh"),
    ("Global", "e", "Open in Editor"),
    ("Global", "\\", "Toggle Sidebar"),
    ("Global", "m", "Focus MR List"),
    ("Global", "b", "Checkout Branch"),
    ("Navigation", "j / ↓", "Move Down"),
    ("Navigation", "k / ↑", "Move Up"),
    ("Navigation", "h / ←", "Scroll Left"),
    ("Navigation", "l / →", "Scroll Right"),
    ("Navigation", "Enter", "Select / Expand"),
    ("Diff View", "t", "Toggle unified / side-by-side"),
    ("Diff View", "c", "Add Comment"),
    ("Diff View", "w", "Toggle Wrap"),
    ("Diff View", "s", "Select Syntax"),
    ("Diff View", "p", "Select Pygments Style"),
    ("Diff View", "a", "Expand All Lines"),
    ("Diff View", "]", "Jump to Next Diff Line"),
    ("Diff View", "[", "Jump to Previous Diff Line"),
    ("Comment Input", "Ctrl+S", "Submit Comment"),
    ("Comment Input", "Ctrl+E", "Open External Editor"),
    ("Comment Input", "Escape", "Cancel"),
    ("Settings", "Ctrl+S", "Save"),
    ("Settings", "Ctrl+E", "Open in Editor"),
    ("Settings", "Escape", "Close"),
    ("Dialogs", "Escape", "Close / Cancel"),
    ("Dialogs", "q", "Close (Comment View)"),
]


class HelpScreen(ModalScreen[None]):
    """キーバインド一覧を表示するモーダルスクリーン。"""

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("escape", "dismiss", "Close"),
        Binding("question_mark", "dismiss", "Close"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="help-container"):
            yield Label("[bold]Keybindings[/bold]", id="help-title")
            table = DataTable(id="keybindings-table")
            yield table

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_columns("Category", "Key", "Action")
        for category, key, action in _KEYBINDINGS:
            table.add_row(category, key, action)

    def action_dismiss(self) -> None:
        self.dismiss()
