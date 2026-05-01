# 作業単位計画 - glreview

## 概要

glreviewは単一デプロイ（ローカルCLIツール）のモノリシックPythonアプリケーションである。
3層アーキテクチャ（TUI層・API層・基盤層）に基づき、依存関係の方向に沿って3つの作業単位に分解する。

## 分解方針

- **単位の粒度**：層ベースの分解。各層を1つの作業単位とする
- **実装順序**：依存関係の下流から上流へ（基盤層 → API層 → TUI層）
- **理由**：各層は明確な責任境界を持ち、下位層のテストが完了してから上位層を実装することで安定した開発が可能

## 作業単位の定義

### Unit 1：Infrastructure（基盤層）

- [ ] ConfigManager - TOML設定ファイルの読み書き
- [ ] GitRepoDetector - gitリモートURLからプロジェクト情報検出
- [ ] Logger - 構造化ロギング（SECURITY-03準拠）
- [ ] データモデル定義 - 全層で共有するdataclass群

**コンポーネント**：ConfigManager, GitRepoDetector, Logger, データモデル（models.py）
**依存先**：なし（外部ライブラリのみ：tomllib, subprocess/git）

### Unit 2：GitLab API Services（API層）

- [ ] GitLabClient - python-gitlabラッパー、認証・接続管理
- [ ] MRService - MR一覧・詳細・差分の取得
- [ ] CommentService - コメントの取得・投稿・リプライ

**コンポーネント**：GitLabClient, MRService, CommentService
**依存先**：Unit 1（ConfigManager, データモデル）

### Unit 3：TUI Application（TUI層）

- [ ] App - メインアプリケーション、レイアウト、CLI引数、キーバインド
- [ ] MRListPanel - MRカテゴリ別ツリー表示・選択操作
- [ ] ContentPanel - Overview/差分表示、行選択、シンタックスハイライト
- [ ] CommentDialog - コメント入力・送信モーダル
- [ ] HelpScreen - キーバインド一覧表示
- [ ] 外部エディタ連携機能

**コンポーネント**：GLReviewApp, MRListPanel, ContentPanel, CommentDialog, HelpScreen
**依存先**：Unit 2（MRService, CommentService）、Unit 1（ConfigManager）

## 必須成果物

- [x] `aidlc-docs/inception/application-design/unit-of-work.md`を生成する
- [x] `aidlc-docs/inception/application-design/unit-of-work-dependency.md`を生成する
- [x] `aidlc-docs/inception/application-design/unit-of-work-story-map.md`を生成する
- [x] コード組織戦略を`unit-of-work.md`に文書化する
- [x] ユニットの境界と依存関係を検証する
- [x] すべての要件（FR/NFR）がユニットに割り当てられていることを確認する

## 設計質問

### 質問 1：コード組織構造

Pythonプロジェクトのディレクトリ構造として以下のどれを希望しますか？

A) フラットパッケージ構造 — `glreview/` 配下に層ごとのモジュールファイルを配置
```
glreview/
├── __init__.py
├── __main__.py
├── app.py           # TUI: App
├── panels.py        # TUI: MRListPanel, ContentPanel
├── dialogs.py       # TUI: CommentDialog, HelpScreen
├── gitlab_client.py # API: GitLabClient
├── mr_service.py    # API: MRService
├── comment_service.py # API: CommentService
├── config.py        # 基盤: ConfigManager
├── git_detector.py  # 基盤: GitRepoDetector
├── logger.py        # 基盤: Logger
├── models.py        # 共通: データモデル
└── styles.tcss      # Textual CSS
```

B) サブパッケージ構造 — 層ごとにサブパッケージを分離
```
glreview/
├── __init__.py
├── __main__.py
├── models.py
├── tui/
│   ├── __init__.py
│   ├── app.py
│   ├── panels.py
│   ├── dialogs.py
│   └── styles.tcss
├── services/
│   ├── __init__.py
│   ├── gitlab_client.py
│   ├── mr_service.py
│   └── comment_service.py
└── infrastructure/
    ├── __init__.py
    ├── config.py
    ├── git_detector.py
    └── logger.py
```

C) その他（以下の[Answer]:タグの後に記述してください）

[Answer]:B

### 質問 2：テストの配置

テストファイルの配置として以下のどれを希望しますか？

A) トップレベルtestsディレクトリ — ソースコードと分離
```
tests/
├── test_config.py
├── test_git_detector.py
├── test_gitlab_client.py
├── test_mr_service.py
├── test_comment_service.py
└── ...
```

B) 各パッケージ内にtestsサブディレクトリ — ソースコードに近接配置
```
glreview/
├── infrastructure/
│   ├── tests/
│   │   ├── test_config.py
│   │   └── ...
```

C) その他（以下の[Answer]:タグの後に記述してください）

[Answer]:B
