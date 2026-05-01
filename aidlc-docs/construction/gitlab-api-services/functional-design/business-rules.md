# UNIT-02: GitLab API Services ビジネスルール

## 概要

GitLab API Servicesのビジネスルール、バリデーションロジック、制約を定義する。

---

## 1. 認証ルール

### BR-AUTH-01: トークン検証

- GitLabClient生成時に `gl.auth()` で認証を検証する
- 認証失敗（401）時は `GitLabAuthError` を送出する
- トークンがAppConfigに未設定（空文字列）の場合、接続を試みずに即座にエラーとする

### BR-AUTH-02: 操作スコープ制限（NFR-04準拠）

- API層は**閲覧とコメント投稿のみ**を提供する
- MRのステータス変更（承認、マージ、クローズ等）のメソッドは実装しない
- python-gitlabのProjectオブジェクトを外部に公開しない（意図しない操作の防止）

---

## 2. MR一覧取得ルール

### BR-MR-01: ステータスフィルタ

- MR一覧は `state="opened"` のMRのみを取得する
- マージ済み・クローズ済みのMRは取得しない

### BR-MR-02: カテゴリ分類の排他性

- 4カテゴリ（自身割当/自身作成/未割当/他者割当）は独立したAPIクエリで取得する
- 「自身以外に割り当てられているMR」は `assignee_id="Any"` で取得後、current_user_idと一致するMRをクライアント側で除外する
- 1つのMRが複数カテゴリに表示される可能性がある（例：自身が作成し、自身に割当）。これはAPI層では制御せず、TUI層の表示責任とする

### BR-MR-03: ページネーション

- 初回は1ページ分（per_page=20）を取得する
- 次ページの有無はpython-gitlabのレスポンスから判定する
- 追加ページの取得はTUI層からの明示的な要求で行う（遅延読み込み）
- 各カテゴリのページ位置は独立して管理する

### BR-MR-04: ソート順

- デフォルトのソート順は `order_by="updated_at", sort="desc"`（更新日時降順）
- ユーザーは設定ファイルで `order_by` を変更可能
- 有効な `order_by` の値: `"updated_at"`, `"created_at"`
- 無効な値が設定された場合はデフォルト（updated_at）にフォールバックする

---

## 3. MR詳細取得ルール

### BR-DETAIL-01: 詳細取得

- `mr_iid`（プロジェクト内のMR番号）で取得する
- 存在しないMR IIDの場合は `MRNotFoundError` を送出する

### BR-DETAIL-02: フィールドマッピング

- `pipeline_status` はMRの `head_pipeline` が存在する場合のみ設定する（存在しない場合はNone）
- `milestone` はMRにマイルストーンが設定されている場合のみタイトルを設定する（未設定の場合はNone）
- `assignee` はアサインされている場合のみusernameを設定する（未アサインの場合はNone）

---

## 4. 差分取得ルール

### BR-DIFF-01: 遅延取得

- ファイル一覧（FileChange）はMR選択時に取得する
- 個別ファイルの差分（FileDiff）はユーザーがファイルを選択した時点で取得する
- 差分の一括取得は行わない

### BR-DIFF-02: ファイルパス照合

- 差分取得時は `new_path` でファイルを照合する
- リネームされたファイルの場合、`old_path` と `new_path` の両方を保持する
- ファイルが見つからない場合は `FileNotFoundInMRError` を送出する

---

## 5. コメント投稿ルール

### BR-COMMENT-01: コメント本文バリデーション

- コメント本文（body）は空文字列・空白のみを許可しない
- 本文が空の場合は `EmptyCommentError` を送出する（API呼び出しは行わない）

### BR-COMMENT-02: インラインコメントのポジション

- インラインコメント投稿時はMRの最新のdiff参照情報（base_sha, head_sha, start_sha）を使用する
- `line_type` は `"new"` または `"old"` のいずれかでなければならない
- `"new"` の場合: `new_line = line, old_line = None`
- `"old"` の場合: `old_line = line, new_line = None`

### BR-COMMENT-03: リプライの整合性

- リプライ投稿時は `discussion_id` が有効であることを確認する
- ディスカッションが見つからない場合は `DiscussionNotFoundError` を送出する

### BR-COMMENT-04: システムノートの除外

- ディスカッション取得時にシステムノート（`note.system == True`）を除外する
- ユーザーが投稿したコメントのみを返す

---

## 6. キャッシュルール

### BR-CACHE-01: キャッシュ対象

| データ | キー | キャッシュ対象 |
|--------|------|---------------|
| MR一覧（カテゴリ別） | — | 対象外（常にAPI呼び出し） |
| MR詳細 | mr_iid | 対象 |
| 変更ファイル一覧 | mr_iid | 対象 |
| ファイル差分 | (mr_iid, file_path) | 対象 |
| ディスカッション | mr_iid | 対象 |

### BR-CACHE-02: キャッシュ無効化トリガー

- **明示的リフレッシュ**: 全キャッシュをクリアする
- **コメント投稿成功時**: 該当MRのディスカッションキャッシュのみクリアする
- **アプリケーション終了時**: メモリ解放により自動的にクリアされる

### BR-CACHE-03: キャッシュの一貫性

- キャッシュヒット時はキャッシュ済みデータをそのまま返す（コピーではなく参照）
- キャッシュミス時はAPI呼び出し後、結果をキャッシュに保存してから返す

---

## 7. エラーハンドリングルール

### BR-ERROR-01: エラー分類

| python-gitlab例外 | 内部エラー | ユーザー向けメッセージ |
|---|---|---|
| `GitlabAuthenticationError` | `GitLabAuthError` | 認証に失敗しました。トークンを確認してください |
| `GitlabGetError` (404) | `MRNotFoundError` / `GitLabProjectNotFoundError` | 指定されたリソースが見つかりません |
| `GitlabGetError` (403) | `GitLabAccessDeniedError` | アクセス権限がありません |
| `GitlabHttpError` | `GitLabConnectionError` | GitLabサーバーへの接続に失敗しました |
| `requests.Timeout` | `GitLabConnectionError` | 接続がタイムアウトしました |
| `requests.ConnectionError` | `GitLabConnectionError` | ネットワーク接続を確認してください |

### BR-ERROR-02: リトライポリシー

- リトライは行わない（Q3: A）
- エラー発生時は即座にユーザーにエラーメッセージを表示する
- エラーメッセージに内部詳細（スタックトレース、API URL等）を含めない（SECURITY-09準拠）

### BR-ERROR-03: エラーログ

- すべてのAPIエラーを構造化ログに記録する（SECURITY-03準拠）
- ログにはエラー種別、HTTPステータスコード、タイムスタンプを含める
- ログにトークンやリクエストヘッダの認証情報を含めない
