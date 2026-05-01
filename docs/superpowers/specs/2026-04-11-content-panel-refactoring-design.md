# content_panel.py リファクタリング設計書

**日付:** 2026-04-11  
**対象:** `glreview/tui/widgets/content_panel.py`（1870行）  
**方針:** Martin Fowler のリファクタリング原則（Extract Module）に基づく複数ファイル分割

---

## 背景・目的

`content_panel.py` が約1870行に膨張し、以下の複数の責務が混在している：

- diff パース・フィルタリング
- シンタックスハイライト（Pygments 連携）
- Overview 表示・コメントヘルパー
- diff 表示用定数・DiffGutter ウィジェット
- ContentPanel ウィジェット（コーディネータ）

責務ごとにモジュールを分割することで、各ファイルの理解・テスト・修正が独立してできるようにする。

---

## 新ファイル構成

```
glreview/tui/widgets/
├── __init__.py           (変更なし: ContentPanel を export)
├── content_panel.py      (ContentPanel クラスのみ残す、~550行)
├── _diff_parser.py       (diff パース・フィルタ、~150行)
├── _syntax.py            (シンタックスハイライト、~120行)
├── _overview.py          (Overview・コメントヘルパー、~110行)
└── _diff_renderer.py     (DiffGutter + 表示定数、~80行)
```

---

## 各モジュールの責務と移動対象

### `_diff_parser.py`

**責務:** unified diff の文字列解析・フィルタリング

移動する定数:
- `_CONTEXT_LINES`
- `_LOAD_MORE_LINES`
- `_TOP_LOAD_SENTINEL`
- `_BOTTOM_LOAD_SENTINEL`

移動する関数:
- `_parse_diff(diff_text)` — diff 文字列をタプルリストに変換
- `_apply_context_filter(parsed, context, forced_ctx_indices)` — コンテキスト行を絞り込み
- `_find_first_last_new_line(parsed)` — 新ファイル側の最初・最後の行番号を返す
- `_format_diff_line(line)` — テスト用レガシー関数（後方互換のため保持）

### `_syntax.py`

**責務:** Pygments を用いたシンタックスハイライト

移動する定数:
- `_SYNTAX_COLORS`（Dracula テーマ準拠カラーマップ）

移動する関数:
- `_build_colors_from_pygments_style(style_name)` — Pygments スタイルから Rich スタイルマップを構築
- `_get_lexer_for_path(file_path)` — ファイルパスから Pygments レキサーを返す
- `_get_token_color(token_type)` — トークンタイプから Rich スタイル文字列を返す（モジュールレベル版）

### `_overview.py`

**責務:** MR Overview 表示テキストの構築・コメント位置の管理

移動する定数:
- `_IMAGE_PATTERN`（正規表現）

移動する関数:
- `_extract_images(text)` — Markdown から画像リンクを抽出
- `_build_overview_text(mr_detail, discussions)` — Overview 表示テキストを構築
- `_get_comment_lines(discussions, file_path)` — インラインコメント行番号集合を返す
- `_build_comment_map(discussions, file_path)` — 行番号→ディスカッションリストのマップを構築

### `_diff_renderer.py`

**責務:** diff 行の表示スタイル定数・テキスト折り返し・ガタービジェット

移動する定数:
- `_DIFF_ADD_STYLE`
- `_DIFF_REM_STYLE`
- `_DIFF_HUNK_STYLE`
- `_DIFF_GAP_STYLE`
- `_LINE_NO_WIDTH`

移動する関数:
- `_wrap_text(text, width)` — テキストを指定幅で折り返す

移動するクラス:
- `DiffGutter` — スクロールバー横のカラーマーカーウィジェット

### `content_panel.py`（残留）

**責務:** ContentPanel コーディネータ

残留するもの:
- `ContentPanel` クラス（全メソッド）
- `_gather_two(coro1, coro2)` — ContentPanel 内部専用の並行実行ユーティリティ

`content_panel.py` の先頭で各サブモジュールから必要なシンボルをインポートする:

```python
from glreview.tui.widgets._diff_parser import (
    _CONTEXT_LINES, _LOAD_MORE_LINES, _TOP_LOAD_SENTINEL, _BOTTOM_LOAD_SENTINEL,
    _parse_diff, _apply_context_filter, _find_first_last_new_line,
)
from glreview.tui.widgets._syntax import (
    _SYNTAX_COLORS, _build_colors_from_pygments_style, _get_lexer_for_path,
)
from glreview.tui.widgets._overview import (
    _build_overview_text, _get_comment_lines, _build_comment_map,
)
from glreview.tui.widgets._diff_renderer import (
    _DIFF_ADD_STYLE, _DIFF_REM_STYLE, _DIFF_HUNK_STYLE, _DIFF_GAP_STYLE,
    _LINE_NO_WIDTH, _wrap_text, DiffGutter,
)
```

---

## インポートの変更方針

### テストファイルの更新

`test_entities.py` と `test_app_utils.py` は内部関数・クラスを `content_panel` から直接インポートしているため、新しいモジュールパスに更新する。

| 現在のインポート元 | 新しいインポート元 |
|---|---|
| `content_panel._parse_diff` | `_diff_parser._parse_diff` |
| `content_panel._apply_context_filter` | `_diff_parser._apply_context_filter` |
| `content_panel._find_first_last_new_line` | `_diff_parser._find_first_last_new_line` |
| `content_panel._format_diff_line` | `_diff_parser._format_diff_line` |
| `content_panel._get_token_color` | `_syntax._get_token_color` |
| `content_panel._get_lexer_for_path` | `_syntax._get_lexer_for_path` |
| `content_panel._build_colors_from_pygments_style` | `_syntax._build_colors_from_pygments_style` |
| `content_panel._build_overview_text` | `_overview._build_overview_text` |
| `content_panel._extract_images` | `_overview._extract_images` |
| `content_panel._get_comment_lines` | `_overview._get_comment_lines` |
| `content_panel._build_comment_map` | `_overview._build_comment_map` |
| `content_panel._wrap_text` | `_diff_renderer._wrap_text` |
| `content_panel.DiffGutter` | `_diff_renderer.DiffGutter` |
| `content_panel.ContentPanel` | `content_panel.ContentPanel`（変更なし） |

後方互換の再エクスポートは設けない（移動先を正とする）。

### 外部インポートは変更なし

- `app.py`: `from glreview.tui.widgets.content_panel import ContentPanel`
- `__init__.py`: `from glreview.tui.widgets.content_panel import ContentPanel`

---

## テスト戦略

- 既存テストのインポートパスを更新するのみ（テストロジックは変更しない）
- リファクタリング後に全テストが通ることを確認する
- 新たなテストは追加しない（振る舞いの変更はないため）

---

## 適用するリファクタリング手法

- **Extract Module** (Fowler): 関連する関数・定数・クラスを独立したモジュールに抽出
- **Move Function** (Fowler): 関数を最も適切な責務を持つモジュールへ移動
- **Move Class** (Fowler): `DiffGutter` を `_diff_renderer.py` に移動
