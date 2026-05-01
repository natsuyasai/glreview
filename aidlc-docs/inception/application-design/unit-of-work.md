# 作業単位定義 - glreview

## 概要

glreviewは単一デプロイのモノリシックPython TUIアプリケーションであり、3層アーキテクチャに基づき3つの作業単位に分解する。実装順序は依存関係の下流から上流へ進める。

## 作業単位一覧

| ユニットID | 名前 | 層 | コンポーネント数 | 依存先 |
|---|---|---|---|---|
| UNIT-01 | Infrastructure | 基盤層 | 4 | なし |
| UNIT-02 | GitLab API Services | API層 | 3 | UNIT-01 |
| UNIT-03 | TUI Application | TUI層 | 5 | UNIT-01, UNIT-02 |

## 実装順序

```
UNIT-01 (Infrastructure) → UNIT-02 (GitLab API Services) → UNIT-03 (TUI Application)
```

---

## UNIT-01：Infrastructure（基盤層）

### 責任

アプリケーション全体の基盤となる設定管理、Git情報検出、ロギング、および共有データモデルを提供する。

### コンポーネント

| コンポーネント | 責任 |
|---|---|
| ConfigManager | TOML設定ファイル（~/.config/glreview/config.toml）の読み書き、デフォルト設定生成、バリデーション |
| GitRepoDetector | カレントディレクトリのgitリモートURL（origin）を解析し、GitLabホストとプロジェクトパスを検出 |
| Logger | 構造化ロギングのセットアップ（SECURITY-03準拠：トークン非出力） |
| データモデル | 全層で共有するdataclass定義（AppConfig, MergeRequestSummary, MergeRequestDetail, FileChange, FileDiff, CommentType, CommentContext, Discussion, Note, NotePosition, GitLabProjectInfo） |

### 対応要件

- FR-07（プロジェクト自動検出）
- NFR-02（認証・設定ファイル管理）
- NFR-03（セルフホスト/SaaS両対応 — URL設定）
- NFR-06（セキュリティ — SECURITY-03, SECURITY-09, SECURITY-12）

### 境界

- 外部依存：`tomllib`（Python 3.11+標準）、`subprocess`（git コマンド）
- 他ユニットへの公開インターフェース：`AppConfig`, `GitLabProjectInfo`, 全データモデル, `ConfigManager`, `GitRepoDetector`, `setup_logging`, `get_logger`

---

## UNIT-02：GitLab API Services（API層）

### 責任

python-gitlabを通じてGitLab APIと通信し、MRの一覧・詳細・差分取得、およびコメント操作を提供する。

### コンポーネント

| コンポーネント | 責任 |
|---|---|
| GitLabClient | python-gitlabのラッパー。認証・接続管理、プロジェクト取得、現在のユーザー情報取得 |
| MRService | MRのカテゴリ別一覧取得（assigned/created/unassigned/others）、MR詳細・変更ファイル・差分の取得 |
| CommentService | MRのディスカッション取得、インラインコメント投稿、ノート投稿、リプライ投稿 |

### 対応要件

- FR-01（MR一覧表示 — API取得部分）
- FR-03（Overview表示 — データ取得部分）
- FR-04（差分表示 — データ取得部分）
- FR-05（コメント機能 — API投稿部分）
- NFR-05（パフォーマンス — API呼び出し最適化）
- NFR-06（セキュリティ — SECURITY-15 エラーハンドリング）

### 境界

- 外部依存：`python-gitlab`
- UNIT-01依存：`ConfigManager`（AppConfig取得）、データモデル（戻り値の型）
- 他ユニットへの公開インターフェース：`GitLabClient`, `MRService`, `CommentService`

---

## UNIT-03：TUI Application（TUI層）

### 責任

Textualフレームワークを使用したマルチペインTUIの構築。ユーザーインタラクション（キーバインド、ツリー操作、コメント入力）を処理し、API層と連携する。

### コンポーネント

| コンポーネント | 責任 |
|---|---|
| GLReviewApp | メインアプリケーション。レイアウト管理、CLI引数解析、グローバルキーバインド、外部エディタ連携 |
| MRListPanel | 左ペイン。MRカテゴリ別ツリー表示、ノード選択・展開操作 |
| ContentPanel | 右ペイン。MR Overview表示、差分表示（Pygmentsハイライト）、行選択、既存コメント表示 |
| CommentDialog | モーダルダイアログ。コメントタイプ選択（インライン/ノート/リプライ）、テキスト入力・送信 |
| HelpScreen | モーダル画面。キーバインド一覧表示 |

### 対応要件

- FR-01（MR一覧表示 — UI表示部分）
- FR-02（MRツリー展開）
- FR-03（Overview表示 — UI表示部分）
- FR-04（差分表示 — UI表示・ハイライト部分）
- FR-04a（外部エディタ連携）
- FR-05（コメント機能 — UI入力部分）
- FR-06（引数によるMR指定起動）
- NFR-07（ユーザビリティ — キーバインド、ヘルプ、レスポンシブ）

### 境界

- 外部依存：`textual`, `pygments`
- UNIT-01依存：`ConfigManager`（エディタ設定取得）
- UNIT-02依存：`MRService`, `CommentService`（データ取得・投稿）

---

## コード組織戦略

サブパッケージ構造を採用し、テストは各パッケージ内に配置する。

```
glreview/                         # トップレベルパッケージ
├── __init__.py                     # パッケージ初期化、バージョン
├── __main__.py                     # エントリーポイント（CLI引数解析）
├── models.py                       # 共有データモデル（dataclass群）
├── tui/                            # UNIT-03: TUI層
│   ├── __init__.py
│   ├── app.py                      # GLReviewApp
│   ├── panels.py                   # MRListPanel, ContentPanel
│   ├── dialogs.py                  # CommentDialog, HelpScreen
│   ├── styles.tcss                 # Textual CSSスタイル
│   └── tests/
│       ├── __init__.py
│       ├── test_app.py
│       ├── test_panels.py
│       └── test_dialogs.py
├── services/                       # UNIT-02: API層
│   ├── __init__.py
│   ├── gitlab_client.py            # GitLabClient
│   ├── mr_service.py               # MRService
│   ├── comment_service.py          # CommentService
│   └── tests/
│       ├── __init__.py
│       ├── test_gitlab_client.py
│       ├── test_mr_service.py
│       └── test_comment_service.py
└── infrastructure/                 # UNIT-01: 基盤層
    ├── __init__.py
    ├── config.py                   # ConfigManager
    ├── git_detector.py             # GitRepoDetector
    ├── logger.py                   # setup_logging, get_logger
    └── tests/
        ├── __init__.py
        ├── test_config.py
        ├── test_git_detector.py
        └── test_logger.py
```

### パッケージング

- `pyproject.toml` をプロジェクトルートに配置
- `pip install` / `pipx install` 対応
- エントリーポイント：`glreview = "glreview.__main__:main"`
- 依存関係バージョンピン留め（SECURITY-10準拠）
