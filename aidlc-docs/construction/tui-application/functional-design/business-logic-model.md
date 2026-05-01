# UNIT-03: TUI Application ビジネスロジックモデル

## 概要

TUI ApplicationはTextualフレームワークを使用したマルチペインTUIであり、5つのコンポーネント（GLReviewApp、MRListPanel、ContentPanel、CommentDialog、HelpScreen）で構成される。UNIT-01（設定）・UNIT-02（API）に依存し、ユーザーインタラクションとデータ表示を担う。

---

## 1. GLReviewApp ビジネスロジック

### 1.1 アプリケーション初期化

```
入力: mr_id (int | None) — CLI引数で指定されたMR ID
処理:
  1. ConfigManager.load() でAppConfigを取得する
  2. setup_logging(config) でロガーを初期化する
  3. GitRepoDetector.get_project_path() でプロジェクトパスを検出する
  4. GitLabClient(config) を生成し、await client.connect() で接続する
  5. MRService(client, project_path) を生成し、await mr_service.load()
  6. CommentService(client, project_path) を生成し、await comment_service.load()
  7. MRListPanel と ContentPanel にサービスインスタンスを渡す
  8. mr_id が指定されている場合、MRListPanel.expand_mr(mr_id) を呼び出す
出力: 初期化済みアプリケーション
エラー時: エラーダイアログ表示（接続失敗、プロジェクト未検出等）
```

### 1.2 レイアウト構成

```
処理:
  1. Horizontal レイアウトで MRListPanel（30%）と ContentPanel（70%）を配置する
  2. MRListPanel は開閉トグル可能（キーバインドで制御）
  3. MRListPanel 閉時は ContentPanel が100%幅に拡張する
  4. Footer にステータス情報を表示する
```

### 1.3 グローバルキーバインド

```
キーバインドマッピング:
  q         → action_quit()       — アプリケーション終了
  ?         → action_show_help()  — HelpScreen表示
  r         → action_refresh()    — MR一覧リフレッシュ（全キャッシュクリア）
  e         → action_open_in_editor() — 外部エディタで現在のファイルを開く
  [         → action_toggle_sidebar() — 左ペイン開閉トグル
```

### 1.4 リフレッシュ

```
処理:
  1. MRService.invalidate_cache() で全キャッシュをクリアする
  2. CommentService.invalidate_cache() でディスカッションキャッシュをクリアする
  3. MRListPanel.refresh_list() でMR一覧を再取得する
  4. ContentPanel の表示をクリアする
```

### 1.5 外部エディタ連携

```
入力: 現在表示中のファイルパスと行番号
処理:
  1. ContentPanel.get_selected_line() で (file_path, line_number) を取得する
  2. 取得できない場合は何もしない
  3. AppConfig.editor の値を取得する（未設定なら環境変数$EDITORにフォールバック）
  4. TUIを一時停止する（app.suspend()）
  5. subprocess で editor +line_number file_path を実行する
  6. エディタ終了後にTUIを復帰する
```

---

## 2. MRListPanel ビジネスロジック

### 2.1 MR一覧取得・ツリー構築

```
処理:
  1. 4カテゴリを並行で取得する（asyncio.gather）:
     - MRService.get_assigned_to_me()
     - MRService.get_created_by_me()
     - MRService.get_unassigned()
     - MRService.get_assigned_to_others()
  2. ツリーのルートに4つのカテゴリノードを作成する:
     - "Assigned to me (N)"
     - "Created by me (N)"
     - "Unassigned (N)"
     - "Others (N)"
     ※ N = 取得件数
  3. 各カテゴリノードの下にMRノードを追加する:
     - 表示形式: "!{iid} {title}"
  4. MR一覧が空のカテゴリは表示するが「(empty)」を表示する
```

### 2.2 MRツリー展開

```
入力: 選択されたMRノード (mr_iid: int)
処理:
  1. MRService.get_mr_changes(mr_iid) で変更ファイル一覧を取得する
  2. MRノードの下に子ノードを作成する:
     a. "Overview" ノード
     b. 各 FileChange のノード（表示: ファイルパス + 変更種別アイコン）
        - 新規ファイル: "+" prefix
        - 削除ファイル: "-" prefix
        - リネーム: "→" 表示 (old_path → new_path)
        - 変更: スペース prefix
  3. 最初の子ノード（Overview）を自動選択する
```

### 2.3 ノード選択イベント

```
入力: Tree.NodeSelected イベント
処理:
  ノードタイプに応じて分岐:
  - カテゴリノード: 何もしない（展開/折りたたみのみ）
  - MRノード（未展開）: expand_mr(mr_iid) を実行
  - "Overview" ノード: ContentPanel.show_overview(mr_iid) を呼び出す
  - ファイルノード: ContentPanel.show_diff(mr_iid, file_path) を呼び出す
```

### 2.4 追加ページ読み込み（遅延読み込み）

```
処理:
  1. カテゴリノードの末尾に「Load more...」ノードを表示する
     （PaginatedResult.has_next_page == True の場合のみ）
  2. 「Load more...」選択時に次ページを取得する
  3. 取得したMRをカテゴリノードに追加する
  4. さらに次ページがある場合は再度「Load more...」を表示する
```

---

## 3. ContentPanel ビジネスロジック

### 3.1 Overview表示

```
入力: mr_iid (int)
処理:
  1. MRService.get_mr_detail(mr_iid) で詳細情報を取得する
  2. CommentService.get_discussions(mr_iid) でディスカッションを取得する
  3. マークダウン風レイアウトで表示する:
     a. タイトル行: "# !{iid} {title}"
     b. メタデータテーブル:
        | 項目       | 値                    |
        |------------|----------------------|
        | Author     | {author}             |
        | Assignee   | {assignee or 未設定}  |
        | Status     | {status}             |
        | Labels     | {labels joined}      |
        | Milestone  | {milestone or なし}   |
        | Pipeline   | {pipeline_status or なし} |
        | URL        | {web_url}            |
        | Created    | {created_at}         |
        | Updated    | {updated_at}         |
     c. 説明セクション: "## Description\n{description}"
     d. ディスカッションセクション: "## Discussions ({count})"
        各ディスカッション:
          - 著者・日時・本文
          - インラインコメントの場合はファイル・行情報を表示
          - リプライはインデント表示
```

### 3.2 差分表示

```
入力: mr_iid (int), file_path (str)
処理:
  1. MRService.get_mr_diff(mr_iid, file_path) で差分を取得する
  2. CommentService.get_discussions(mr_iid) でディスカッションを取得する
  3. 差分テキストをPygmentsでシンタックスハイライトする:
     - ファイル拡張子からlexerを推定する
     - 追加行は緑背景、削除行は赤背景
     - ハンクヘッダ（@@行）は青色
  4. 表示モードに応じてフォーマットする:
     a. unified: 1カラムで上から下へ表示
     b. side-by-side: 左に旧ファイル、右に新ファイルを並列表示
  5. 既存のインラインコメントがある行にコメントアイコン/マーカーを表示する
  6. カーソルで行選択可能にする（コメント投稿のため）
```

### 3.3 表示モード切替

```
キーバインド: t (toggle)
処理:
  1. unified ↔ side-by-side を切り替える
  2. 現在の差分を新しいモードで再描画する
  3. 切替はセッション中のみ有効（デフォルトは常にunified）
```

### 3.4 行選択

```
処理:
  1. 差分表示中にj/k（または矢印キー）で行を移動する
  2. 選択中の行をハイライト表示する
  3. c キーでCommentDialogを開く（選択行の情報を渡す）
```

---

## 4. CommentDialog ビジネスロジック

### 4.1 ダイアログ表示

```
入力: CommentContext（mr_iid, comment_type, file_path, line, line_type, discussion_id）
処理:
  1. コメントタイプに応じたUIを表示する:
     - INLINE: ファイルパスと行番号を表示 + TextArea
     - NOTE: MR全体へのコメント + TextArea
     - REPLY: 元のコメント本文を引用表示 + TextArea
  2. TextAreaにフォーカスを設定する
```

### 4.2 コメント送信

```
入力: ユーザーが入力したテキスト
処理:
  1. テキストが空でないことを確認する
  2. comment_type に応じてAPIを呼び出す:
     - INLINE: CommentService.add_inline_comment(mr_iid, file_path, line, body, line_type)
     - NOTE: CommentService.add_note(mr_iid, body)
     - REPLY: CommentService.reply_to_discussion(mr_iid, discussion_id, body)
  3. 成功時: ダイアログを閉じ、ContentPanelの表示を更新する
  4. 失敗時: エラーダイアログを表示する
```

### 4.3 外部エディタでの入力

```
キーバインド: Ctrl+E（TextArea内で）
処理:
  1. 現在のTextArea内容をテンポラリファイルに書き出す
  2. TUIを一時停止し、外部エディタでテンポラリファイルを開く
  3. エディタ終了後、テンポラリファイルの内容をTextAreaに反映する
  4. テンポラリファイルを削除する
```

---

## 5. HelpScreen ビジネスロジック

### 5.1 ヘルプ表示

```
処理:
  1. 全キーバインド一覧をカテゴリ別に表示する:
     - グローバル: q(終了), ?(ヘルプ), r(リフレッシュ), e(エディタ), [(サイドバー)
     - ナビゲーション: j/k(上下), Enter(選択/展開)
     - 差分表示: t(unified/side-by-side切替), c(コメント)
     - コメント入力: Ctrl+E(外部エディタ), Escape(キャンセル), Ctrl+S(送信)
  2. Escape または ? でヘルプを閉じる
```

---

## 6. データフロー概要

```
ユーザー操作 (キーバインド)
    |
    v
GLReviewApp (グローバルキーバインド処理)
    |
    +---> MRListPanel (ツリー操作)
    |         |
    |         | ノード選択イベント
    |         v
    |     ContentPanel (コンテンツ表示)
    |         |
    |         | コメント操作
    |         v
    |     CommentDialog (モーダル入力)
    |
    +---> HelpScreen (モーダル表示)
    |
    | API呼び出し (async)
    v
MRService / CommentService (UNIT-02)
    |
    v
GitLabClient → GitLab API
```
