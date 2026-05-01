# UNIT-01: Infrastructure コードサマリー

## 生成されたファイル一覧

### プロジェクト設定

| ファイル | 説明 |
|---|---|
| `pyproject.toml` | パッケージ設定、依存関係定義、エントリーポイント（`glreview` コマンド） |

### アプリケーションコード

| ファイル | 説明 |
|---|---|
| `glreview/__init__.py` | パッケージ初期化、バージョン定義（`0.1.0`） |
| `glreview/__main__.py` | エントリーポイント、CLI引数解析（`mr_id` オプション引数）、グローバルエラーハンドラ |
| `glreview/models.py` | 全共有データクラス定義 |
| `glreview/infrastructure/__init__.py` | サブパッケージ初期化、公開API（`ConfigManager`, `GitRepoDetector`, `get_logger`, `setup_logging`） |
| `glreview/infrastructure/config.py` | `ConfigManager` — 設定ファイル読み込み・バリデーション・セットアップウィザード |
| `glreview/infrastructure/git_detector.py` | `GitRepoDetector` — gitリモートURL検出・解析 |
| `glreview/infrastructure/logger.py` | `setup_logging`, `get_logger`, `TokenMaskingFilter` — ロギング基盤 |

### テストコード

| ファイル | 説明 |
|---|---|
| `glreview/infrastructure/tests/__init__.py` | テストパッケージ初期化 |
| `glreview/infrastructure/tests/test_models.py` | 全dataclassの生成テスト・不変条件テスト（39テスト） |
| `glreview/infrastructure/tests/test_config.py` | ConfigManager の読み込み・バリデーション・パス解決テスト（16テスト） |
| `glreview/infrastructure/tests/test_git_detector.py` | GitRepoDetector のURL解析・リモート検出・エラーケーステスト（21テスト） |
| `glreview/infrastructure/tests/test_logger.py` | TokenMaskingFilter・setup_logging・get_logger・ログクリーンアップテスト（16テスト） |
| `glreview/infrastructure/tests/test_integration.py` | 実ファイル・実gitリポジトリを使った統合テスト（12テスト） |

## モデル一覧（models.py）

| クラス | 種別 | 説明 |
|---|---|---|
| `AppConfig` | dataclass | アプリケーション設定（gitlab_url, token, editor, log_level, theme, remote_name） |
| `GitLabProjectInfo` | dataclass | Gitリモートから解析したGitLab接続情報（host, project_path） |
| `MergeRequestSummary` | dataclass | MR一覧表示用軽量データ |
| `MergeRequestDetail` | dataclass | MR詳細表示用フルデータ |
| `FileChange` | dataclass | MR変更ファイルのメタ情報 |
| `FileDiff` | dataclass | ファイル差分コンテンツ（unified diff形式） |
| `CommentType` | Enum | コメント種別（INLINE / NOTE / REPLY） |
| `CommentContext` | dataclass | コメント投稿コンテキスト（種別に応じた不変条件を検証） |
| `NotePosition` | dataclass | インラインコメントの位置情報 |
| `Note` | dataclass | 個別コメント/ノート |
| `Discussion` | dataclass | ディスカッションスレッド（1つ以上のNoteを含む） |

## 公開例外クラス（git_detector.py）

| 例外クラス | 発生条件 |
|---|---|
| `GitCommandNotFoundError` | git バイナリが見つからない / タイムアウト |
| `NotAGitRepositoryError` | gitリポジトリ外で実行 |
| `NoRemoteConfiguredError` | リモートが1つも設定されていない |
| `RemoteNotFoundError` | 指定したリモート名が存在しない |
| `URLParseError` | リモートURLを解析できない |

## セキュリティ対応サマリー

| ルール | 実装箇所 | 内容 |
|---|---|---|
| SECURITY-03 | `logger.py: TokenMaskingFilter` | `glpat-` パターン・20文字以上の英数字をREDACTED置換 |
| SECURITY-09 | `config.py`, `git_detector.py` | ユーザー向けエラーは汎用メッセージのみ、詳細はDEBUGログ |
| SECURITY-12 | `config.py: _write_config()` | config.toml を 0600、設定ディレクトリを 0700 に設定（Unix系のみ） |

## テストカバレッジの概要

- **合計テスト数**: 約104テスト（ユニット92 + 統合12）
- **テスト戦略**: ユニットテストはモック中心、統合テストは実ファイル・実gitリポジトリ使用
- **カバレッジ目標**: 80%以上
