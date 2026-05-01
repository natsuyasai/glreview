"""SyntaxSelectDialog — シンタックスハイライト言語選択モーダルダイアログ。"""

from __future__ import annotations

from typing import ClassVar

from pygments.lexers import get_all_lexers
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, Label, OptionList
from textual.widgets.option_list import Option, Separator

# 言語リストをモジュールロード時に1回だけ構築してキャッシュする
_LANGUAGE_LIST: list[tuple[str, str]] = sorted(
    [(name, aliases[0]) for name, aliases, _, _ in get_all_lexers() if aliases],
    key=lambda x: x[0].lower(),
)

# 特別オプションの ID
_OPT_AUTO = "__auto__"
_OPT_NONE = "__none__"


def _make_options(query: str) -> list[Option | Separator]:
    """クエリに一致する言語オプションリストを返す。"""
    options: list[Option | Separator] = [
        Option("(auto-detect from filename)", id=_OPT_AUTO),
        Option("(no highlight)", id=_OPT_NONE),
        Separator(),
    ]
    q = query.lower().strip()
    matched = (
        [(name, alias) for name, alias in _LANGUAGE_LIST if q in name.lower() or q in alias.lower()]
        if q
        else _LANGUAGE_LIST
    )
    for name, alias in matched[:100]:
        options.append(Option(f"{name}  [dim]\\[{alias}][/dim]", id=alias))
    return options


class SyntaxSelectDialog(ModalScreen[str | None]):
    """シンタックスハイライト言語を選択するモーダルダイアログ。

    dismiss() の引数:
        _OPT_AUTO  : ファイル拡張子から自動検出に戻す
        _OPT_NONE  : ハイライト無効
        alias str  : Pygments レキサーのエイリアス名（例: "python", "go"）
        None       : キャンセル（変更なし）
    """

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("escape", "cancel", "Cancel"),
        Binding("j", "list_down", "Down", show=False),
        Binding("k", "list_up", "Up", show=False),
    ]

    def __init__(self, current_name: str | None = None) -> None:
        super().__init__()
        self._current_name = current_name

    def compose(self) -> ComposeResult:
        subtitle = f"Current: {self._current_name}" if self._current_name else "Current: (auto)"
        with Vertical(id="syntax-select-container"):
            yield Label("[bold]🎨 Select Syntax Language[/bold]", id="syntax-select-title")
            yield Label(subtitle, id="syntax-select-subtitle")
            yield Input(placeholder="Filter languages...", id="syntax-filter")
            yield OptionList(*_make_options(""), id="syntax-option-list")
            yield Label(
                "[dim]Enter: select  Esc: cancel  j/k or ↑↓: move[/dim]",
                id="syntax-select-hint",
            )

    def on_mount(self) -> None:
        self.query_one("#syntax-filter", Input).focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        """フィルタ入力が変わったらオプションリストを更新する。"""
        option_list = self.query_one("#syntax-option-list", OptionList)
        option_list.clear_options()
        for opt in _make_options(event.value):
            if isinstance(opt, Separator):
                option_list.add_option(opt)
            else:
                option_list.add_option(opt)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Enterキーでフォーカスをリストに移す。"""
        self.query_one("#syntax-option-list", OptionList).focus()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """オプション選択時にダイアログを閉じてエイリアスを返す。"""
        self.dismiss(event.option_id)

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_list_down(self) -> None:
        self.query_one("#syntax-option-list", OptionList).action_cursor_down()

    def action_list_up(self) -> None:
        self.query_one("#syntax-option-list", OptionList).action_cursor_up()


# 外部から参照できるように定数を公開する
AUTO_OPTION_ID = _OPT_AUTO
NONE_OPTION_ID = _OPT_NONE
