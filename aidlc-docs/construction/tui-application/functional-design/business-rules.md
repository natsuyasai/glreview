# UNIT-03: TUI Application ビジネスルール

## 概要

TUI Applicationのビジネスルール、キーバインドマッピング、状態遷移、バリデーションロジックを定義する。

---

## 1. レイアウトルール

### BR-LAYOUT-01: デフォルトペイン比率

- 左ペイン（MRListPanel）: 30%幅
- 右ペイン（ContentPanel）: 70%幅
- ターミナルサイズ変更に追従する（Textualのレスポンシブ機能）

### BR-LAYOUT-02: 左ペイン開閉トグル

- `[` キーで左ペインの表示/非表示を切り替える
- 非表示時は ContentPanel が100%幅に拡張する
- 再表示時は元の30%幅に復帰する
- 初期状態は表示（opened）

---

## 2. キーバインドルール

### BR-KEY-01: グローバルキーバインド（常時有効）

| キー | アクション | 説明 |
|------|-----------|------|
| `q` | action_quit | アプリケーション終了 |
| `?` | action_show_help | HelpScreen表示/非表示 |
| `r` | action_refresh | MR一覧リフレッシュ（全キャッシュクリア） |
| `e` | action_open_in_editor | 外部エディタで現在のファイルを開く |
| `[` | action_toggle_sidebar | 左ペイン開閉トグル |

### BR-KEY-02: ナビゲーションキーバインド（ツリー/差分表示時）

| キー | アクション | 説明 |
|------|-----------|------|
| `j` / `↓` | カーソル下移動 | 次の行/ノードへ移動 |
| `k` / `↑` | カーソル上移動 | 前の行/ノードへ移動 |
| `Enter` | 選択/展開 | ノード選択またはMR展開 |

### BR-KEY-03: 差分表示キーバインド

| キー | アクション | 説明 |
|------|-----------|------|
| `t` | toggle_diff_mode | unified ↔ side-by-side切替 |
| `c` | action_add_comment | 選択行にコメントを追加 |

### BR-KEY-04: コメント入力キーバインド

| キー | アクション | 説明 |
|------|-----------|------|
| `Ctrl+S` | action_submit | コメント送信 |
| `Escape` | action_cancel | コメントキャンセル（ダイアログ閉じる） |
| `Ctrl+E` | open_external_editor | 外部エディタで編集 |

### BR-KEY-05: モーダル画面共通

- モーダル（HelpScreen, CommentDialog）表示中はバックグラウンドのキーバインドは無効
- `Escape` でモーダルを閉じる

---

## 3. MR一覧表示ルール

### BR-MRLIST-01: カテゴリ表示順

1. Assigned to me
2. Created by me
3. Unassigned
4. Others

### BR-MRLIST-02: MRノード表示形式

- フォーマット: `!{iid} {title}`
- タイトルが長い場合はペイン幅に合わせてトランケート（末尾 `...`）

### BR-MRLIST-03: 空カテゴリの表示

- MRが0件のカテゴリも表示する
- カテゴリラベルに `(0)` を付与し、子ノードは表示しない

### BR-MRLIST-04: 遅延読み込み

- 各カテゴリ初回は20件取得
- `has_next_page == True` の場合、カテゴリ末尾に「Load more...」ノードを表示
- 「Load more...」選択時に次ページを取得し、既存リストに追加

---

## 4. コンテンツ表示ルール

### BR-CONTENT-01: Overview表示構成

1. タイトル行: `# !{iid} {title}`
2. メタデータテーブル（Author, Assignee, Status, Labels, Milestone, Pipeline, URL, Created, Updated）
3. 説明セクション
4. ディスカッションセクション（カウント付き）

### BR-CONTENT-02: 差分表示モード

- **unified**（デフォルト）: 1カラム、追加行=緑背景、削除行=赤背景
- **side-by-side**: 左=旧ファイル、右=新ファイル
- `t` キーで切替、セッション中のみ有効

### BR-CONTENT-03: シンタックスハイライト

- Pygmentsでファイル拡張子からlexerを自動推定する
- 推定不可の場合はプレーンテキストとして表示する
- ハンクヘッダ（`@@` 行）は青色で表示する

### BR-CONTENT-04: インラインコメント表示

- 差分表示中、既存のインラインコメントがある行にマーカーを表示する
- マーカー選択時にコメント内容を展開表示する

---

## 5. コメント投稿ルール

### BR-COMMENT-01: コメントタイプの決定

| 操作元 | コメントタイプ | CommentContext |
|--------|-------------|----------------|
| 差分表示で行選択 + `c` | INLINE | file_path, line, line_type |
| Overview表示で `c` | NOTE | mr_iid のみ |
| ディスカッション上で `c` | REPLY | discussion_id |

### BR-COMMENT-02: 空コメント防止

- 送信前にテキストが空でないことを確認する
- 空の場合はダイアログ内にバリデーションメッセージを表示し、送信しない

### BR-COMMENT-03: 送信後の画面更新

- コメント送信成功後、ContentPanel の表示を自動更新する
  - Overview表示中: ディスカッション一覧を再取得
  - 差分表示中: インラインコメントを再取得

---

## 6. 外部エディタルール

### BR-EDITOR-01: エディタ解決順序

1. `AppConfig.editor` の設定値
2. 環境変数 `$EDITOR`
3. フォールバック: `vi`

### BR-EDITOR-02: ファイル差分閲覧時のエディタ起動

- 差分表示中に `e` キーでエディタ起動
- `editor +{line_number} {file_path}` 形式で起動する
- 行番号はカーソル位置の行番号を使用する

### BR-EDITOR-03: コメント入力時のエディタ起動

- CommentDialog内で `Ctrl+E` でエディタ起動
- テンポラリファイルにTextArea内容を書き出し、エディタで編集
- エディタ終了後にテンポラリファイル内容をTextAreaに反映
- テンポラリファイルは使用後に削除する

---

## 7. エラー表示ルール

### BR-ERROR-01: エラーダイアログ

- API通信エラー、認証エラー等はモーダルダイアログで表示する
- ダイアログに「OK」ボタンまたは `Enter`/`Escape` で閉じられる
- エラーメッセージはUNIT-02のカスタム例外の `message` フィールドを使用する

### BR-ERROR-02: 初期化エラー

- アプリケーション起動時の初期化エラー（接続失敗、プロジェクト未検出）はエラーダイアログ表示後、アプリケーションを終了する

---

## 8. 状態遷移

### BR-STATE-01: アプリケーション状態

```
INITIALIZING → READY → (操作中) → QUITTING

INITIALIZING:
  - 設定読み込み、API接続、サービス初期化
  - エラー時 → ERROR_DIALOG → QUITTING

READY:
  - MR一覧表示済み、ユーザー操作受付中
  - MR選択 → MR展開 → コンテンツ表示

操作中:
  - Overview表示 / 差分表示 / コメント入力
  - エラー時 → ERROR_DIALOG → READY に戻る
```

### BR-STATE-02: フォーカス管理

- 起動時: MRListPanel（左ペイン）にフォーカス
- MR展開後: ContentPanel（右ペイン）にフォーカス
- Tab キーで左右ペイン間のフォーカス切替
- モーダル表示時: モーダルにフォーカス固定
