# サービス定義とオーケストレーション

## サービス一覧

| サービス        | 層      | 責任                                |
| --------------- | ------- | ----------------------------------- |
| MRService       | API層   | MR一覧・詳細・差分の取得            |
| CommentService  | API層   | コメントの取得・投稿・リプライ      |
| ConfigManager   | 基盤層  | 設定ファイルの読み書き              |
| GitRepoDetector | 基盤層  | gitリモートからプロジェクト情報検出 |

## オーケストレーションパターン

### 起動フロー

```
CLI引数解析
    |
    v
ConfigManager.load()
    |
    v
GitRepoDetector.get_project_path()
    |
    v
GitLabClient.connect()
    |
    v
GLReviewApp(mr_id=引数のMR ID or None)
    |
    v
MRListPanel.load_merge_requests()
    |  (mr_id指定時)
    +---> MRListPanel.expand_mr(mr_id)
```

### MR一覧取得フロー

```
MRListPanel
    |
    | load_merge_requests()
    v
MRService
    |
    |-- get_assigned_to_me()
    |-- get_created_by_me()
    |-- get_unassigned()
    +-- get_assigned_to_others()
    |
    v
GitLabClient (python-gitlab API呼び出し)
```

### MR詳細表示フロー

```
MRListPanel (ノード選択)
    |
    | on_tree_node_selected()
    v
ContentPanel
    |
    |-- show_overview(mr_id) --> MRService.get_mr_detail()
    |                        --> CommentService.get_discussions()
    |
    +-- show_diff(mr_id, file_path) --> MRService.get_mr_diff()
                                    --> CommentService.get_discussions()
```

### コメント投稿フロー

```
ContentPanel (行選択 + コメントキー)
    |
    v
CommentDialog (モーダル表示)
    |
    | action_submit()
    v
CommentService
    |
    |-- add_inline_comment()  (差分行へのコメント)
    |-- add_note()            (MR全体へのノート)
    +-- reply_to_discussion() (既存コメントへのリプライ)
    |
    v
GitLabClient (python-gitlab API呼び出し)
    |
    v
ContentPanel (表示更新)
```

### 外部エディタ連携フロー

```
ContentPanel (エディタキー押下)
    |
    v
App.action_open_in_editor()
    |
    | ConfigManager.editor の値を使用
    | ($EDITOR フォールバック)
    v
subprocess: editor +line_number file_path
    |
    v
TUIを一時停止 -> エディタ終了後に復帰
```

## TUI層とAPI層の接続

- TUI層はAPI層のサービスに**直接依存**する（シンプルな依存注入）
- API層のサービスはアプリケーション起動時にインスタンス化され、TUIウィジェットに渡される
- API呼び出しは**非同期**（Textualのworkerまたはasyncio）で実行し、UIブロッキングを防ぐ
- エラーはAPI層でキャッチし、TUI層にはユーザーフレンドリーなメッセージとして伝播する
