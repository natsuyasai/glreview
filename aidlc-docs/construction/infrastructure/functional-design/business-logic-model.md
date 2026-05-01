# UNIT-01: Infrastructure ビジネスロジックモデル

## 1. ConfigManager ビジネスロジック

### 1.1 設定ファイルパス解決

```
入力: なし（または明示的パス指定）
処理:
  1. 明示的パスが指定されている場合 → そのパスを使用
  2. 指定なしの場合 → ~/.config/glreview/config.toml を使用
  3. XDG_CONFIG_HOME が設定されている場合 → $XDG_CONFIG_HOME/glreview/config.toml を使用
出力: 解決された設定ファイルパス（Path）
```

### 1.2 設定ファイル読み込み

```
入力: 設定ファイルパス（Path）
処理:
  1. ファイルが存在するか確認
  2. 存在しない場合 → SetupWizardRequiredError を発生
  3. 存在する場合 → tomllib でパース
  4. パース失敗時 → ConfigParseError を発生
  5. パース成功 → AppConfig dataclass にマッピング
  6. バリデーションを実行
  7. バリデーション失敗 → ConfigValidationError を発生（エラー詳細リスト付き）
出力: AppConfig
```

### 1.3 対話式セットアップウィザード

```
入力: 設定ファイルパス（Path）
処理:
  1. 設定ファイルが既に存在する場合 → 上書き確認プロンプト
  2. GitLab URL の入力を求める（デフォルト: https://gitlab.com）
  3. パーソナルアクセストークンの入力を求める（入力マスク付き）
  4. 入力されたURL・トークンでGitLab APIへの接続テストを実行
  5. 接続テスト失敗 → エラー表示し再入力を求める
  6. 接続テスト成功 → TOML形式で設定ファイルを書き込み
  7. ファイルパーミッションを0600に設定（Unix系のみ）
  8. ディレクトリが存在しない場合は作成（パーミッション0700）
出力: 生成された設定ファイルパス
```

### 1.4 設定バリデーション

```
入力: AppConfig
処理:
  1. gitlab_url が有効なURL形式か検証（http:// または https://）
  2. token が空でないか検証
  3. token がプレースホルダー値でないか検証
  4. log_level が有効な値か検証（DEBUG, INFO, WARNING, ERROR, CRITICAL）
  5. theme が有効なTextualテーマ名か検証（dark, light, textual-dark, textual-light等）
  6. editor が空の場合はデフォルト（$EDITOR → vi）にフォールバック
出力: list[str]（バリデーションエラーメッセージのリスト、空ならOK）
```

### 1.5 デフォルト設定生成

```
入力: gitlab_url (str), token (str)
処理:
  1. AppConfig を以下のデフォルト値で生成:
     - gitlab_url: 引数で受け取った値
     - token: 引数で受け取った値
     - editor: os.environ.get("EDITOR", "vi")
     - log_level: "INFO"
     - theme: "dark"
     - remote_name: ""（空文字 = 自動検出）
出力: AppConfig
```

## 2. GitRepoDetector ビジネスロジック

### 2.1 リモートURL検出（フォールバックチェーン）

```
入力: working_dir (Path | None)
処理:
  1. working_dir が None の場合 → カレントディレクトリを使用
  2. git rev-parse --is-inside-work-tree で git リポジトリか確認
  3. git リポジトリでない場合 → NotAGitRepositoryError を発生
  4. AppConfig.remote_name が設定されている場合:
     a. git remote get-url {remote_name} を実行
     b. 成功 → そのURLを返す
     c. 失敗 → RemoteNotFoundError を発生
  5. AppConfig.remote_name が未設定（空文字）の場合:
     a. git remote get-url origin を実行
     b. 成功 → そのURLを返す
     c. 失敗 → git remote を実行してリモート一覧を取得
     d. リモートが1つ以上存在 → 最初のリモートのURLを返す
     e. リモートが0個 → NoRemoteConfiguredError を発生
出力: リモートURL文字列
```

### 2.2 GitLab情報解析

```
入力: remote_url (str)
処理:
  1. SSH形式の判定と解析:
     パターン: git@{host}:{project_path}.git
     正規表現: ^git@([^:]+):(.+?)(?:\.git)?$
  2. HTTPS形式の判定と解析:
     パターン: https://{host}/{project_path}.git
     正規表現: ^https?://([^/]+)/(.+?)(?:\.git)?$
  3. SSH（ポート指定あり）形式の判定と解析:
     パターン: ssh://git@{host}:{port}/{project_path}.git
     正規表現: ^ssh://git@([^:/]+)(?::\d+)?/(.+?)(?:\.git)?$
  4. いずれにもマッチしない場合 → URLParseError を発生
  5. project_path の正規化:
     - 先頭・末尾のスラッシュを除去
     - .git サフィックスを除去（未除去の場合）
  6. サブグループ対応: project_path は group/subgroup/.../project 形式を許容
出力: GitLabProjectInfo(host, project_path)
```

### 2.3 プロジェクトパス取得（便利メソッド）

```
入力: なし
処理:
  1. detect_remote_url() を呼び出し
  2. parse_gitlab_info() を呼び出し
  3. project_path を返す
出力: str（project_path）
```

## 3. Logger ビジネスロジック

### 3.1 ロギングセットアップ

```
入力: config (AppConfig)
処理:
  1. ログディレクトリ（~/.config/glreview/logs/）の存在確認・作成
  2. ログファイル名: glreview_{YYYY-MM-DD}.log
  3. RotatingFileHandler を設定:
     - maxBytes: 5MB
     - backupCount: 3
  4. フォーマッタ設定:
     - フォーマット: {timestamp} [{level}] {name}: {message}
     - 日付フォーマット: ISO 8601
  5. TokenMaskingFilter をハンドラに追加
  6. ルートロガーの設定:
     - レベル: config.log_level
     - ハンドラ: RotatingFileHandler
出力: logging.Logger（ルートロガー）
```

### 3.2 トークンマスキングフィルタ

```
入力: ログレコード
処理:
  1. ログメッセージ内でトークンパターンを検索:
     - glpat-で始まる文字列（GitLab Personal Access Token）
     - 20文字以上の英数字連続文字列
  2. マッチした部分を "***REDACTED***" に置換
  3. ログレコードの args も同様に検査・置換
出力: フィルタ適用済みログレコード（常にTrue=出力許可）
```

### 3.3 ロガー取得

```
入力: name (str)
処理:
  1. logging.getLogger(f"glreview.{name}") を返す
出力: logging.Logger
```
