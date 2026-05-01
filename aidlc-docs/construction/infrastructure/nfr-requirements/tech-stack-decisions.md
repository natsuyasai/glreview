# UNIT-01: Infrastructure テックスタック決定

## Python ランタイム

| 項目 | 決定 |
|---|---|
| 最低バージョン | Python 3.11 |
| 根拠 | `tomllib` が標準ライブラリに搭載（外部依存不要）、2027年10月までサポート |
| pyproject.toml指定 | `requires-python = ">=3.11"` |

## 依存ライブラリ

### 直接依存（UNIT-01スコープ）

| ライブラリ | 用途 | バージョン方針 | 備考 |
|---|---|---|---|
| (標準ライブラリ) tomllib | TOML設定ファイルの読み込み | Python 3.11+ 標準 | 外部依存なし |
| (標準ライブラリ) subprocess | gitコマンド実行 | Python 標準 | 外部依存なし |
| (標準ライブラリ) logging | ロギング | Python 標準 | 外部依存なし |
| (標準ライブラリ) dataclasses | データモデル定義 | Python 標準 | 外部依存なし |
| (標準ライブラリ) pathlib | パス操作 | Python 標準 | 外部依存なし |
| (標準ライブラリ) getpass | トークン入力マスク | Python 標準 | セットアップウィザード用 |
| (標準ライブラリ) re | 正規表現（URL解析） | Python 標準 | 外部依存なし |
| (標準ライブラリ) os | 環境変数、パーミッション | Python 標準 | 外部依存なし |
| (標準ライブラリ) enum | 列挙型 | Python 標準 | CommentType |

### プロジェクト全体の依存（UNIT-01が関与する部分）

| ライブラリ | 用途 | バージョン方針 |
|---|---|---|
| python-gitlab | GitLab API通信（UNIT-02で使用） | 互換範囲指定（例: `>=4.0,<5.0`） |
| textual | TUIフレームワーク（UNIT-03で使用） | 互換範囲指定 |
| pygments | シンタックスハイライト（UNIT-03で使用） | 互換範囲指定 |

### 開発依存

| ライブラリ | 用途 | バージョン方針 |
|---|---|---|
| pytest | テストフレームワーク | 互換範囲指定 |
| pytest-cov | カバレッジ計測 | 互換範囲指定 |
| ruff | リンター＋フォーマッター | 互換範囲指定 |

## TOML設定ファイルの読み書き

| 操作 | 方法 |
|---|---|
| 読み込み | `tomllib`（Python 3.11+ 標準） |
| 書き込み | 文字列テンプレートによるTOML生成（tomli-wやtomlkit等の外部ライブラリは不使用） |
| 根拠 | 設定ファイルの構造が単純（ネストは1段）であり、文字列テンプレートで十分。外部依存を最小化 |

## subprocessによるgitコマンド実行

| 項目 | 決定 |
|---|---|
| 実行方法 | `subprocess.run()` with `capture_output=True, text=True, timeout=30` |
| シェル使用 | `shell=False`（セキュリティ上の理由） |
| エンコーディング | UTF-8 |
| エラー判定 | `returncode != 0` で判定、`CalledProcessError` はキャッチ |

## ロギング構成

| 項目 | 決定 |
|---|---|
| ハンドラ | `logging.handlers.RotatingFileHandler` |
| ファイルサイズ | 5MB / 3世代 |
| フォーマット | `{asctime} [{levelname}] {name}: {message}` (style="{") |
| 日付フォーマット | `%Y-%m-%dT%H:%M:%S` (ISO 8601) |
| フィルタ | TokenMaskingFilter（カスタム） |
| 古いログ削除 | 起動時に30日以上前の `glreview_*.log` を削除 |

## パッケージング

| 項目 | 決定 |
|---|---|
| ビルドシステム | `pyproject.toml` + `setuptools` or `hatchling` |
| エントリーポイント | `glreview = "glreview.__main__:main"` |
| インストール方法 | `pip install` / `pipx install` |
| ソース配布 | sdist + wheel |

## ディレクトリ構成（UNIT-01部分）

```
glreview/
├── __init__.py
├── __main__.py
├── models.py                    # 共有データモデル
└── infrastructure/
    ├── __init__.py
    ├── config.py                # ConfigManager
    ├── git_detector.py          # GitRepoDetector
    ├── logger.py                # setup_logging, get_logger
    └── tests/
        ├── __init__.py
        ├── test_config.py       # 単体（モック）+ 統合（実ファイル）
        ├── test_git_detector.py # 単体（モック）+ 統合（実gitリポ）
        └── test_logger.py       # 単体（モック）+ 統合（実ログ出力）
```
