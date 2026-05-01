# コンポーネント依存関係

## 依存関係マトリックス

| コンポーネント    | 依存先                                          |
| ----------------- | ----------------------------------------------- |
| App               | MRListPanel, ContentPanel, ConfigManager        |
| MRListPanel       | MRService                                       |
| ContentPanel      | MRService, CommentService                       |
| CommentDialog     | CommentService                                  |
| HelpScreen        | （依存なし）                                    |
| MRService         | GitLabClient                                    |
| CommentService    | GitLabClient                                    |
| GitLabClient      | ConfigManager                                   |
| ConfigManager     | （依存なし）                                    |
| GitRepoDetector   | （依存なし）                                    |
| Logger            | ConfigManager                                   |

## 依存関係図

```
+-------------------------------------------------------------+
|                        App (Textual)                        |
|  +------------------------+  +----------------------------+ |
|  |    MRListPanel         |  |      ContentPanel          | |
|  |                        |  |                            | |
|  +----------+-------------+  +-----+----------+----------+ |
|             |                      |          |            |
+-------------------------------------------------------------+
              |                      |          |
              v                      v          v
+---------------------+  +----------------------------+
|     MRService       |  |     CommentService         |
|                     |  |                            |
+----------+----------+  +----------+-----------------+
           |                        |
           v                        v
    +-------------------------------+
    |        GitLabClient           |
    |    (python-gitlab wrapper)    |
    +-------------------------------+
                  |
                  v
    +-------------------------------+
    |       ConfigManager           |
    |   (~/.config/glreview/)     |
    +-------------------------------+

    +-------------------------------+
    |      GitRepoDetector          |
    |    (git remote URL parser)    |
    +-------------------------------+
```

## データフロー

```
ユーザー操作 (キー入力)
         |
         v
+------------------+
|   TUI層          |
|   App            |  <--- キーバインド処理
|   MRListPanel    |  <--- MR選択
|   ContentPanel   |  <--- 差分/Overview表示
|   CommentDialog  |  <--- コメント入力
+------------------+
         |
         | (メッセージ/イベント)
         v
+------------------+
|   API層          |
|   MRService      |  <--- MR CRUD
|   CommentService |  <--- コメント CRUD
+------------------+
         |
         | (python-gitlab API呼び出し)
         v
+------------------+
|   GitLabClient   |  <--- 認証・接続管理
+------------------+
         |
         | (HTTPS / REST API)
         v
+------------------+
|   GitLab Server  |
+------------------+
```

## 通信パターン

- **TUI層 -> API層**：直接メソッド呼び出し（非同期）
- **API層 -> GitLabClient**：直接メソッド呼び出し（同期、python-gitlab）
- **GitLabClient -> GitLab Server**：HTTPS REST API（python-gitlabが管理）
- **TUI層内**：Textualのメッセージシステム（イベント駆動）
