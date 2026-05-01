# UNIT-01: Infrastructure コード生成計画

## ユニットコンテキスト

- **ユニット**: UNIT-01 Infrastructure（基盤層）
- **プロジェクトタイプ**: グリーンフィールド（モノリス）
- **ワークスペースルート**: `c:\Users\fuku\Desktop\glreview`
- **コード配置**: `glreview/infrastructure/` および `glreview/models.py`

## 依存関係

- 外部依存: なし（すべてPython標準ライブラリ）
- 他ユニットへの公開: AppConfig, GitLabProjectInfo, 全データモデル, ConfigManager, GitRepoDetector, setup_logging, get_logger

## 対応要件

- FR-07（プロジェクト自動検出）
- FR-04a（外部エディタ連携 — 設定提供部分）
- NFR-02（認証・設定ファイル管理）
- NFR-03（セルフホスト/SaaS両対応 — URL設定）
- NFR-06（セキュリティ — SECURITY-03, SECURITY-09, SECURITY-12）

## 生成ステップ

### プロジェクト構造セットアップ

- [x] ステップ1: プロジェクト基盤ファイルの作成
  - `pyproject.toml` — パッケージ設定、依存関係定義、エントリーポイント
  - `glreview/__init__.py` — パッケージ初期化、バージョン定義
  - `glreview/__main__.py` — エントリーポイント、CLI引数解析、グローバルエラーハンドラ
  - `glreview/infrastructure/__init__.py` — サブパッケージ初期化、公開API定義
  - `glreview/infrastructure/tests/__init__.py`

### データモデル

- [x] ステップ2: 共有データモデルの生成
  - `glreview/models.py` — 全dataclass定義（AppConfig, GitLabProjectInfo, MergeRequestSummary, MergeRequestDetail, FileChange, FileDiff, CommentType, CommentContext, Discussion, Note, NotePosition）
  - domain-entities.md の型制約・不変条件に準拠

### ビジネスロジック

- [x] ステップ3: ConfigManager の生成
  - `glreview/infrastructure/config.py`
  - 設定ファイルパス解決（XDG対応）
  - TOML読み込み・AppConfigマッピング
  - バリデーション（BR-VAL-01〜04）
  - セットアップウィザード（対話式、接続テスト付き）
  - デフォルト設定生成
  - ファイルパーミッション管理（SECURITY-12）

- [x] ステップ4: GitRepoDetector の生成
  - `glreview/infrastructure/git_detector.py`
  - リモートURL検出（フォールバックチェーン: origin → 最初のremote → 設定指定）
  - SSH/HTTPS/SSH+ポート の3パターン解析
  - サブグループ対応
  - カスタム例外クラス（NotAGitRepositoryError, NoRemoteConfiguredError, RemoteNotFoundError, URLParseError, GitCommandNotFoundError）
  - タイムアウト30秒

- [x] ステップ5: Logger の生成
  - `glreview/infrastructure/logger.py`
  - setup_logging(): RotatingFileHandler（5MB/3世代）、ログディレクトリ作成
  - TokenMaskingFilter: glpat-パターン・長い英数字列のマスキング（SECURITY-03）
  - get_logger(): 名前付きロガー取得
  - 古いログファイル（30日以上前）の自動削除

### ユニットテスト

- [x] ステップ6: データモデルのユニットテスト
  - `glreview/infrastructure/tests/test_models.py`
  - 各dataclassの生成テスト
  - CommentContext の不変条件テスト

- [x] ステップ7: ConfigManager のユニットテスト
  - `glreview/infrastructure/tests/test_config.py`
  - 設定ファイル読み込み（モック）
  - バリデーション（各ルールのテスト）
  - デフォルト設定生成
  - パス解決ロジック
  - 設定ファイル不存在時のエラー

- [x] ステップ8: GitRepoDetector のユニットテスト
  - `glreview/infrastructure/tests/test_git_detector.py`
  - SSH/HTTPS/SSH+ポート各パターンの解析テスト（モック）
  - サブグループパスの解析テスト
  - リモートフォールバックチェーンのテスト（モック）
  - 各エラーケース（git未初期化、remote未設定等）のテスト

- [x] ステップ9: Logger のユニットテスト
  - `glreview/infrastructure/tests/test_logger.py`
  - TokenMaskingFilter のマスキングテスト
  - setup_logging のハンドラ設定テスト（モック）
  - get_logger の名前付きロガーテスト

### 統合テスト

- [x] ステップ10: 統合テスト
  - `glreview/infrastructure/tests/test_integration.py`
  - 実際のTOMLファイル読み書き（tmpdir使用）
  - 実際のgitリポジトリでのリモートURL検出（tmpdir使用）
  - 実際のログファイル出力確認（tmpdir使用）

### ドキュメント

- [x] ステップ11: コードサマリードキュメント
  - `aidlc-docs/construction/infrastructure/code/code-summary.md`
  - 生成されたファイル一覧と概要
  - テストカバレッジの概要
