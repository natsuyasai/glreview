# アプリケーション設計 - glreview

## 概要

GitLab MRの閲覧・コメント機能を提供するPython TUIアプリケーション。
lazygit風のマルチペインレイアウトで、ターミナル上でMRのレビュー作業を効率的に行える。

**技術スタック：**

- **言語**：Python
- **TUIフレームワーク**：Textual
- **GitLab API**：python-gitlab
- **シンタックスハイライト**：Pygments
- **設定ファイル**：TOML

## アーキテクチャ

3層構成のアプリケーション：

```
+-------------------------------------------------------------+
|                     TUI層 (Textual)                         |
|  App / MRListPanel / ContentPanel / CommentDialog / Help    |
+-------------------------------------------------------------+
|                     API層 (Services)                        |
|  MRService / CommentService / GitLabClient                  |
+-------------------------------------------------------------+
|                     基盤層 (Infrastructure)                  |
|  ConfigManager / GitRepoDetector / Logger                   |
+-------------------------------------------------------------+
```

## コンポーネント一覧

### TUI層（5コンポーネント）

| コンポーネント | 責任                                       |
| -------------- | ------------------------------------------ |
| App            | レイアウト管理、グローバルキーバインド、CLI引数 |
| MRListPanel    | MRカテゴリ別ツリー表示、選択操作            |
| ContentPanel   | Overview/差分表示、行選択、コメントトリガー |
| CommentDialog  | コメント入力・送信モーダル                  |
| HelpScreen     | キーバインド一覧表示                        |

### API層（3コンポーネント）

| コンポーネント | 責任                               |
| -------------- | ---------------------------------- |
| GitLabClient   | python-gitlabラッパー、認証・接続  |
| MRService      | MR一覧・詳細・差分取得             |
| CommentService | コメント取得・投稿・リプライ       |

### 基盤層（3コンポーネント）

| コンポーネント  | 責任                                |
| --------------- | ----------------------------------- |
| ConfigManager   | TOML設定ファイル読み書き            |
| GitRepoDetector | gitリモートURLからプロジェクト検出  |
| Logger          | 構造化ロギング（SECURITY-03準拠）   |

## 主要フロー

### 起動フロー

1. CLI引数解析（MR ID指定の有無）
2. ConfigManager.load() で設定読み込み
3. GitRepoDetector.get_project_path() でプロジェクト検出
4. GitLabClient.connect() でAPI接続
5. GLReviewApp 起動
6. MRListPanel.load_merge_requests() でMR一覧取得
7. MR ID指定時は即座にそのMRを展開

### MR閲覧フロー

1. MRListPanel でカテゴリツリーからMRを選択
2. ツリー展開でOverview選択肢 + 変更ファイル一覧を表示
3. 項目選択で ContentPanel にOverviewまたは差分を表示
4. 差分表示時はPygmentsによるシンタックスハイライト + 既存コメント表示

### コメント投稿フロー

1. ContentPanel で差分の行を選択
2. コメントキー押下で CommentDialog をモーダル表示
3. コメントタイプ（インライン/ノート/リプライ）に応じた入力
4. CommentService 経由でGitLab APIに投稿
5. ContentPanel の表示を更新

### 外部エディタ連携フロー

1. ContentPanel でエディタキー押下
2. 設定のeditor値（$EDITORフォールバック）でエディタ起動
3. 該当ファイル・該当行にジャンプ
4. エディタ終了後にTUIに復帰

## 依存関係

```
App --> MRListPanel --> MRService --> GitLabClient --> ConfigManager
    --> ContentPanel --> MRService
                    --> CommentService --> GitLabClient
    --> CommentDialog --> CommentService
```

- TUI層はAPI層に直接依存（シンプルな依存注入）
- API呼び出しは非同期（Textual worker）でUIブロッキングを防止
- エラーはAPI層でキャッチし、ユーザーフレンドリーなメッセージとして伝播

## セキュリティ考慮事項

- トークンは設定ファイルに保存、ファイルパーミッション0600推奨（SECURITY-12）
- トークンをログに出力しない（SECURITY-03）
- エラーメッセージに内部詳細を含めない（SECURITY-09）
- 外部API呼び出しに明示的なエラーハンドリング（SECURITY-15）

## 詳細ドキュメント

- [components.md](components.md) - コンポーネント詳細定義
- [component-methods.md](component-methods.md) - メソッドシグネチャとデータモデル
- [services.md](services.md) - サービス定義とオーケストレーションパターン
- [component-dependency.md](component-dependency.md) - 依存関係マトリックスとデータフロー
