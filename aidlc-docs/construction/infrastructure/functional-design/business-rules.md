# UNIT-01: Infrastructure ビジネスルール

## 1. 設定管理ルール

### BR-CFG-01: 設定ファイルパス解決

| 項目 | 内容 |
|---|---|
| ルール | 設定ファイルパスは XDG_CONFIG_HOME > デフォルトパス の優先順で解決する |
| デフォルトパス | `~/.config/glreview/config.toml` |
| XDG対応 | `$XDG_CONFIG_HOME/glreview/config.toml` |
| 明示指定 | ConfigManager(config_path=Path) で任意パスを指定可能 |

### BR-CFG-02: トークン取得

| 項目 | 内容 |
|---|---|
| ルール | トークンは設定ファイルからのみ取得する |
| ソース | `config.toml` の `[auth]` セクション内 `token` フィールド |
| 環境変数 | 使用しない |

### BR-CFG-03: 初回起動時の挙動

| 項目 | 内容 |
|---|---|
| ルール | 設定ファイルが存在しない場合、対話式セットアップウィザードを起動する |
| ウィザードの流れ | GitLab URL入力 → トークン入力 → 接続テスト → 設定ファイル生成 |
| 接続テスト失敗時 | エラーメッセージを表示し再入力を求める |
| 生成後 | アプリケーションを通常起動する |

### BR-CFG-04: 設定ファイルフォーマット

| 項目 | 内容 |
|---|---|
| フォーマット | TOML |
| 必須フィールド | `gitlab_url`, `token` |
| オプションフィールド | `editor`, `log_level`, `theme`, `remote_name` |

**TOML構造**:

```toml
[gitlab]
url = "https://gitlab.com"

[auth]
token = "glpat-xxxxxxxxxxxxxxxxxxxx"

[editor]
command = "vi"

[logging]
level = "INFO"

[appearance]
theme = "dark"

[git]
remote_name = ""
```

### BR-CFG-05: デフォルト値

| フィールド | デフォルト値 | 備考 |
|---|---|---|
| gitlab_url | `https://gitlab.com` | ウィザードで変更可能 |
| token | （なし — 必須入力） | |
| editor | `$EDITOR` → `vi` | 環境変数が未設定の場合vi |
| log_level | `INFO` | |
| theme | `dark` | Textualテーマ名 |
| remote_name | `""` (空文字) | 空 = 自動検出 |

## 2. バリデーションルール

### BR-VAL-01: GitLab URL バリデーション

| 検証項目 | ルール | エラーメッセージ |
|---|---|---|
| プロトコル | `http://` または `https://` で始まること | "GitLab URLはhttp://またはhttps://で始まる必要があります" |
| 空チェック | 空文字列でないこと | "GitLab URLは必須です" |
| 末尾スラッシュ | 自動除去（バリデーションではなく正規化） | — |

### BR-VAL-02: トークン バリデーション

| 検証項目 | ルール | エラーメッセージ |
|---|---|---|
| 空チェック | 空文字列でないこと | "アクセストークンは必須です" |
| プレースホルダー | `"your-token-here"`, `"xxx"` 等でないこと | "アクセストークンにプレースホルダー値が設定されています" |
| 形式 | 警告のみ：`glpat-` で始まることを推奨 | 警告: "GitLabトークンは通常glpat-で始まります" |

### BR-VAL-03: ログレベル バリデーション

| 検証項目 | ルール | エラーメッセージ |
|---|---|---|
| 有効値 | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` のいずれか（大文字小文字不問） | "無効なログレベルです: {value}" |

### BR-VAL-04: テーマ バリデーション

| 検証項目 | ルール | エラーメッセージ |
|---|---|---|
| 有効値 | Textualの組み込みテーマ名であること | "無効なテーマ名です: {value}" |

## 3. Git リモート検出ルール

### BR-GIT-01: リモートURL検出フォールバック

```
優先順位:
  1. AppConfig.remote_name が設定されている場合 → そのリモート名を使用
  2. remote_name が空の場合:
     a. "origin" リモートを試行
     b. origin が存在しない場合 → 最初に見つかったリモートを使用
     c. リモートが0個の場合 → エラー
```

### BR-GIT-02: リモートURL解析パターン

| パターン名 | 形式 | 例 |
|---|---|---|
| SSH標準 | `git@{host}:{path}.git` | `git@gitlab.com:group/subgroup/project.git` |
| HTTPS | `https://{host}/{path}.git` | `https://gitlab.com/group/subgroup/project.git` |
| SSH+ポート | `ssh://git@{host}:{port}/{path}.git` | `ssh://git@gitlab.example.com:2222/group/project.git` |

### BR-GIT-03: プロジェクトパス正規化

| 処理 | 説明 |
|---|---|
| `.git` サフィックス除去 | `group/project.git` → `group/project` |
| 先頭スラッシュ除去 | `/group/project` → `group/project` |
| 末尾スラッシュ除去 | `group/project/` → `group/project` |
| サブグループ対応 | `group/sub1/sub2/project` をそのまま保持 |

### BR-GIT-04: gitリポジトリ検出

| 条件 | 挙動 |
|---|---|
| gitリポジトリ内 | 正常に処理を続行 |
| gitリポジトリ外 | `NotAGitRepositoryError` を発生 |
| gitコマンド未インストール | `GitCommandNotFoundError` を発生 |

## 4. ロギングルール

### BR-LOG-01: ログファイル管理

| 項目 | 値 |
|---|---|
| ディレクトリ | `~/.config/glreview/logs/` |
| ファイル名 | `glreview_{YYYY-MM-DD}.log` |
| ローテーション | 5MB / 3世代 |
| パーミッション | ディレクトリ: 0700, ファイル: 0600 |

### BR-LOG-02: トークンマスキング（SECURITY-03）

| マスク対象 | パターン | 置換先 |
|---|---|---|
| GitLabトークン | `glpat-` で始まる文字列 | `***REDACTED***` |
| 長い英数字列 | 20文字以上の連続英数字 | `***REDACTED***` |

**マスキング適用範囲**: ログメッセージ本文および引数（args）

### BR-LOG-03: ログフォーマット

```
{timestamp} [{level}] {name}: {message}
```

- タイムスタンプ: ISO 8601形式（YYYY-MM-DDTHH:MM:SS）
- レベル: DEBUG/INFO/WARNING/ERROR/CRITICAL
- 名前: `glreview.{module_name}`

## 5. セキュリティルール

### BR-SEC-01: ファイルパーミッション（SECURITY-12）

| 対象 | パーミッション | 備考 |
|---|---|---|
| config.toml | 0600 | トークンを含むため |
| logs/ ディレクトリ | 0700 | |
| ログファイル | 0600 | |
| 設定ディレクトリ | 0700 | |

**注**: Windows環境ではパーミッション設定をスキップする（os.name != "nt" の場合のみ適用）

### BR-SEC-02: エラーメッセージ制限（SECURITY-09）

| ルール | 詳細 |
|---|---|
| トークン非表示 | エラーメッセージにトークン値を含めない |
| パス制限 | フルパスではなくファイル名のみを表示 |
| スタックトレース | DEBUG レベルでのみ出力 |

### BR-SEC-03: セットアップウィザードのトークン入力

| ルール | 詳細 |
|---|---|
| 入力マスク | トークン入力時に画面に値を表示しない（getpassまたは同等） |
| メモリ | 入力後、不要になったトークン変数は明示的にクリアしない（Pythonの仕様上困難なため、ファイルへの永続化で管理） |
