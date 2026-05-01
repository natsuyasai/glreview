"""StyleSelectDialog — Pygments カラースタイル選択モーダルダイアログ。"""

from __future__ import annotations

from typing import ClassVar

from pygments.styles import get_all_styles
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, Label, OptionList
from textual.widgets.option_list import Option, Separator

# スタイルリストをモジュールロード時に1回だけ構築してキャッシュする
_STYLE_LIST: list[str] = sorted(get_all_styles())

# デフォルト（内蔵カラーマップ）を表すID
DEFAULT_OPTION_ID = "__default__"


def _make_options(query: str) -> list[Option | Separator]:
    """クエリに一致するスタイルオプションリストを返す。"""
    options: list[Option | Separator] = [
        Option("(default — built-in Dracula palette)", id=DEFAULT_OPTION_ID),
        Separator(),
    ]
    q = query.lower().strip()
    matched = [s for s in _STYLE_LIST if q in s.lower()] if q else _STYLE_LIST
    for style_name in matched:
        options.append(Option(style_name, id=style_name))
    return options


class StyleSelectDialog(ModalScreen[str | None]):
    """Pygments 組み込みカラースタイルを選択するモーダルダイアログ。

    dismiss() の引数:
        DEFAULT_OPTION_ID : 内蔵 Dracula パレットに戻す
        style_name str    : Pygments スタイル名（例: "monokai", "nord"）
        None              : キャンセル（変更なし）
    """

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("escape", "cancel", "Cancel"),
        Binding("j", "list_down", "Down", show=False),
        Binding("k", "list_up", "Up", show=False),
    ]

    def __init__(self, current_style: str = "") -> None:
        super().__init__()
        self._current_style = current_style

    def compose(self) -> ComposeResult:
        subtitle = (
            f"Current: {self._current_style}" if self._current_style else "Current: (default)"
        )
        with Vertical(id="style-select-container"):
            yield Label("[bold]🎨 Select Pygments Color Style[/bold]", id="style-select-title")
            yield Label(subtitle, id="style-select-subtitle")
            yield Input(placeholder="Filter styles...", id="style-filter")
            yield OptionList(*_make_options(""), id="style-option-list")
            yield Label(
                "[dim]Enter: select  Esc: cancel  j/k or ↑↓: move[/dim]",
                id="style-select-hint",
            )

    def on_mount(self) -> None:
        self.query_one("#style-filter", Input).focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        option_list = self.query_one("#style-option-list", OptionList)
        option_list.clear_options()
        for opt in _make_options(event.value):
            option_list.add_option(opt)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.query_one("#style-option-list", OptionList).focus()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(event.option_id)

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_list_down(self) -> None:
        self.query_one("#style-option-list", OptionList).action_cursor_down()

    def action_list_up(self) -> None:
        self.query_one("#style-option-list", OptionList).action_cursor_up()
