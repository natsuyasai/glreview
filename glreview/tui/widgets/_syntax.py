"""シンタックスハイライト（Pygments 連携）。"""

from __future__ import annotations

from typing import Any

from pygments.lexers import get_lexer_for_filename as _get_lexer_for_filename
from pygments.token import Token as _Token
from pygments.util import ClassNotFound as _ClassNotFound

# シンタックスハイライト用カラーマッピング（Dracula テーマ準拠）
_SYNTAX_COLORS: dict[Any, str] = {
    _Token.Keyword: "bold #ff79c6",
    _Token.Keyword.Constant: "#bd93f9",
    _Token.Keyword.Type: "#8be9fd",
    _Token.Keyword.Namespace: "bold #ff79c6",
    _Token.String: "#f1fa8c",
    _Token.String.Escape: "#ff79c6",
    _Token.String.Interpol: "#ff79c6",
    _Token.String.Doc: "#6272a4",
    _Token.Comment: "#6272a4",
    _Token.Name.Builtin: "#8be9fd",
    _Token.Name.Function: "#50fa7b",
    _Token.Name.Function.Magic: "#50fa7b",
    _Token.Name.Class: "#8be9fd",
    _Token.Name.Decorator: "#50fa7b",
    _Token.Name.Exception: "#ff5555",
    _Token.Name.Constant: "#bd93f9",
    _Token.Name.Namespace: "#8be9fd",
    _Token.Name.Attribute: "#50fa7b",
    _Token.Literal.Number: "#bd93f9",
    _Token.Operator: "#ff79c6",
    _Token.Operator.Word: "bold #ff79c6",
    _Token.Punctuation: "#f8f8f2",
    _Token.Generic.Deleted: "#ff5555",
    _Token.Generic.Inserted: "#50fa7b",
    _Token.Generic.Heading: "bold #f8f8f2",
}


def _build_colors_from_pygments_style(style_name: str) -> dict[Any, str]:
    """Pygments 組み込みスタイルから Rich スタイル文字列マップを構築する。

    変換できない場合は空 dict を返す（呼び出し元が _SYNTAX_COLORS にフォールバック）。
    """
    try:
        from pygments.styles import get_style_by_name

        style_cls = get_style_by_name(style_name)
        colors: dict[Any, str] = {}
        for token, style_def in style_cls:
            parts: list[str] = []
            if style_def["bold"]:
                parts.append("bold")
            if style_def["italic"]:
                parts.append("italic")
            if style_def["color"]:
                parts.append(f"#{style_def['color']}")
            if parts:
                colors[token] = " ".join(parts)
        return colors
    except Exception:
        return {}


def _get_lexer_for_path(file_path: str | None) -> Any | None:
    """ファイルパスから Pygments レキサーを返す。対応言語なければ None。"""
    if not file_path:
        return None
    try:
        return _get_lexer_for_filename(file_path, stripnl=True)
    except _ClassNotFound:
        return None


def _get_token_color(token_type: Any) -> str | None:
    """Pygments トークンタイプを親クラスまで辿り、Rich スタイル文字列を返す。"""
    t = token_type
    while t is not None:
        color = _SYNTAX_COLORS.get(t)
        if color is not None:
            return color
        parent = t.parent
        if parent is t:
            break
        t = parent
    return None
