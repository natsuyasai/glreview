# UNIT-03: TUI Application フロントエンドコンポーネント設計

## 概要

Textualフレームワークを使用したTUIコンポーネントの階層、Props/状態定義、インタラクションフローを設計する。

---

## 1. コンポーネント階層

```
GLReviewApp (App)
  |
  +-- Header (組み込み) — アプリ名表示
  |
  +-- Horizontal (レイアウトコンテナ)
  |     |
  |     +-- MRListPanel (Widget, 30%幅, トグル可能)
  |     |     └── Tree[TreeNodeData] — MRカテゴリ・ファイルツリー
  |     |
  |     +-- ContentPanel (Widget, 70%幅)
  |           +-- (OVERVIEW時) Static/RichLog — Overview表示
  |           +-- (DIFF時) RichLog — 差分表示（ハイライト付き）
  |           +-- (LOADING時) LoadingIndicator — ローディング表示
  |
  +-- Footer (組み込み) — キーバインドヒント表示
  |
  +-- (モーダル) CommentDialog (ModalScreen)
  |     +-- Label — コメントタイプ表示
  |     +-- TextArea — コメント入力
  |     +-- Horizontal — ボタン群
  |           +-- Button "Submit" (Ctrl+S)
  |           +-- Button "Cancel" (Escape)
  |
  +-- (モーダル) HelpScreen (ModalScreen)
  |     └── DataTable — キーバインド一覧テーブル
  |
  +-- (モーダル) ErrorDialog (ModalScreen)
        +-- Label — エラーメッセージ
        +-- Button "OK"
```

---

## 2. 各コンポーネントの詳細

### 2.1 GLReviewApp

**Props（初期化パラメータ）:**

| パラメータ | 型 | 説明 |
|---|---|---|
| mr_id | int \| None | CLI引数で指定されたMR ID |

**状態:**

| 状態 | 型 | 初期値 | 説明 |
|---|---|---|---|
| sidebar_visible | bool | True | 左ペインの表示状態 |
| mr_service | MRService | — | 初期化時に設定 |
| comment_service | CommentService | — | 初期化時に設定 |
| config | AppConfig | — | 初期化時に設定 |

**Textual CSS:**
```css
GLReviewApp {
    layout: horizontal;
}
```

**BINDINGS:**
```python
BINDINGS = [
    Binding("q", "quit", "Quit"),
    Binding("question_mark", "show_help", "Help"),
    Binding("r", "refresh", "Refresh"),
    Binding("e", "open_in_editor", "Editor"),
    Binding("left_square_bracket", "toggle_sidebar", "Toggle Sidebar"),
]
```

---

### 2.2 MRListPanel

**Props:**

| パラメータ | 型 | 説明 |
|---|---|---|
| mr_service | MRService | MR取得サービス |

**状態:**

| 状態 | 型 | 初期値 | 説明 |
|---|---|---|---|
| category_pages | dict[MRCategory, int] | 各カテゴリ=1 | カテゴリ別の現在ページ |
| selected_mr_iid | int \| None | None | 選択中のMR IID |
| expanded_mrs | set[int] | {} | 展開済みMR IIDの集合 |

**インタラクションフロー:**
```
ユーザー操作: ノード選択
  |
  +-- カテゴリノード → 展開/折りたたみのみ
  +-- MRノード（未展開） → expand_mr(iid) → 子ノード追加
  +-- MRノード（展開済み） → 折りたたみ
  +-- Overviewノード → post_message(ShowOverview(iid))
  +-- ファイルノード → post_message(ShowDiff(iid, file_path))
  +-- Load moreノード → 次ページ取得 → ノード追加
```

**カスタムメッセージ:**
```python
class ShowOverview(Message):
    mr_iid: int

class ShowDiff(Message):
    mr_iid: int
    file_path: str
```

---

### 2.3 ContentPanel

**Props:**

| パラメータ | 型 | 説明 |
|---|---|---|
| mr_service | MRService | MR取得サービス |
| comment_service | CommentService | コメントサービス |

**状態:**

| 状態 | 型 | 初期値 | 説明 |
|---|---|---|---|
| view_state | ContentViewState | EMPTY | 現在の表示状態 |
| diff_mode | DiffViewMode | UNIFIED | 差分表示モード |
| current_mr_iid | int \| None | None | 表示中のMR IID |
| current_file_path | str \| None | None | 表示中のファイルパス |
| selected_line | int \| None | None | 選択中の行番号 |
| selected_line_type | str \| None | None | "new" or "old" |

**インタラクションフロー:**
```
ShowOverview メッセージ受信
  → view_state = LOADING
  → MRService.get_mr_detail() + CommentService.get_discussions()
  → view_state = OVERVIEW
  → Overview描画

ShowDiff メッセージ受信
  → view_state = LOADING
  → MRService.get_mr_diff() + CommentService.get_discussions()
  → view_state = DIFF
  → 差分描画（Pygmentsハイライト + インラインコメントマーカー）

t キー
  → diff_mode 切替
  → 現在の差分を再描画

c キー（差分表示時）
  → get_selected_line() で行情報取得
  → CommentDialog をpush（INLINE）

c キー（Overview表示時）
  → CommentDialog をpush（NOTE）
```

---

### 2.4 CommentDialog

**Props:**

| パラメータ | 型 | 説明 |
|---|---|---|
| comment_context | CommentContext | コメントのコンテキスト情報 |
| comment_service | CommentService | コメント投稿サービス |
| editor_command | str | 外部エディタコマンド |

**状態:**

| 状態 | 型 | 初期値 | 説明 |
|---|---|---|---|
| submitting | bool | False | 送信処理中フラグ |

**Textual CSS:**
```css
CommentDialog {
    width: 80%;
    height: 60%;
    align: center middle;
    background: $surface;
    border: thick $primary;
    padding: 1 2;
}
```

**インタラクションフロー:**
```
表示時
  → comment_type に応じたヘッダー表示
  → TextArea にフォーカス

Ctrl+S（送信）
  → submitting = True
  → テキストバリデーション
  → 空なら警告表示
  → API呼び出し（comment_type に応じて分岐）
  → 成功: ダイアログ閉じる + 画面更新メッセージ送信
  → 失敗: エラー表示
  → submitting = False

Ctrl+E（外部エディタ）
  → テンポラリファイル作成
  → app.suspend() + subprocess
  → エディタ終了後、内容をTextAreaに反映
  → テンポラリファイル削除

Escape（キャンセル）
  → ダイアログを閉じる
```

---

### 2.5 HelpScreen

**状態:** なし（静的表示）

**Textual CSS:**
```css
HelpScreen {
    width: 70%;
    height: 80%;
    align: center middle;
    background: $surface;
    border: thick $primary;
    padding: 1 2;
}
```

**表示内容:**
```
+------------------+--------------------------------+
| Key              | Action                         |
+------------------+--------------------------------+
| Global                                            |
+------------------+--------------------------------+
| q                | Quit                           |
| ?                | Toggle Help                    |
| r                | Refresh                        |
| e                | Open in Editor                 |
| [                | Toggle Sidebar                 |
| Tab              | Switch Focus                   |
+------------------+--------------------------------+
| Navigation                                        |
+------------------+--------------------------------+
| j / ↓            | Move Down                      |
| k / ↑            | Move Up                        |
| Enter            | Select / Expand                |
+------------------+--------------------------------+
| Diff View                                         |
+------------------+--------------------------------+
| t                | Toggle unified / side-by-side  |
| c                | Add Comment                    |
+------------------+--------------------------------+
| Comment Input                                     |
+------------------+--------------------------------+
| Ctrl+S           | Submit Comment                 |
| Ctrl+E           | Open External Editor           |
| Escape           | Cancel                         |
+------------------+--------------------------------+
```

---

### 2.6 ErrorDialog

**Props:**

| パラメータ | 型 | 説明 |
|---|---|---|
| error_message | str | エラーメッセージ |

**Textual CSS:**
```css
ErrorDialog {
    width: 60%;
    height: auto;
    max-height: 50%;
    align: center middle;
    background: $error;
    border: thick $error;
    padding: 1 2;
}
```

---

## 3. Textual CSS スタイル（styles.tcss）

```css
/* メインレイアウト */
#main-container {
    layout: horizontal;
    height: 100%;
}

/* 左ペイン */
MRListPanel {
    width: 30%;
    height: 100%;
    border-right: thick $primary;
}

MRListPanel.-hidden {
    display: none;
}

/* 右ペイン */
ContentPanel {
    width: 1fr;
    height: 100%;
}

/* 差分表示の色 */
.diff-add {
    background: #1a3a1a;
    color: #88cc88;
}

.diff-remove {
    background: #3a1a1a;
    color: #cc8888;
}

.diff-hunk {
    color: #6688cc;
    text-style: bold;
}

.diff-selected-line {
    background: $accent;
}

/* インラインコメントマーカー */
.comment-marker {
    color: $warning;
}
```

---

## 4. API統合ポイント

| コンポーネント | 使用するAPIメソッド |
|---|---|
| MRListPanel | MRService.get_assigned_to_me/created_by_me/unassigned/assigned_to_others |
| MRListPanel | MRService.get_mr_changes |
| ContentPanel | MRService.get_mr_detail, get_mr_diff |
| ContentPanel | CommentService.get_discussions |
| CommentDialog | CommentService.add_inline_comment, add_note, reply_to_discussion |
| GLReviewApp | MRService.invalidate_cache, CommentService.invalidate_cache |
