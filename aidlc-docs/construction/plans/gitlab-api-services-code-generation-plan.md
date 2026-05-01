# UNIT-02: GitLab API Services コード生成計画

## ユニットコンテキスト

- **ユニット**: UNIT-02 GitLab API Services（API層）
- **プロジェクトタイプ**: グリーンフィールド（モノリス）
- **ワークスペースルート**: `c:\Users\fuku\Desktop\glreview`
- **コード配置**: `glreview/services/`

## 依存関係

- **UNIT-01依存**: `AppConfig`（ConfigManager経由）、全データモデル（`glreview/models.py`）、`get_logger`（Logger）
- **外部依存**: `python-gitlab==<最新安定版>`、`asyncio`（標準ライブラリ）
- **テスト依存追加**: `pytest-asyncio==<最新安定版>`

## 対応要件

- FR-01（MR一覧表示 — API取得部分）
- FR-03（Overview表示 — データ取得部分）
- FR-04（差分表示 — データ取得部分）
- FR-05（コメント機能 — API投稿部分）
- NFR-05（パフォーマンス — API呼び出し最適化）
- NFR-06（セキュリティ — SECURITY-15 エラーハンドリング）

## 公開インターフェース（UNIT-03向け）

- `GitLabClient` — 認証・接続管理
- `MRService` — MR一覧・詳細・差分取得
- `CommentService` — ディスカッション取得・コメント投稿

---

## 生成ステップ

### サービスパッケージ初期化

- [x] ステップ1: `glreview/services/` パッケージ初期化
  - `glreview/services/__init__.py` — 公開API定義（GitLabClient, MRService, CommentService, エラークラス群）
  - `glreview/services/tests/__init__.py` — テストパッケージ初期化

### カスタム例外・共通型

- [x] ステップ2: `glreview/services/exceptions.py` の生成
  - `GLReviewAPIError`（基底クラス、`message: str`フィールド付き）
  - `GitLabAuthError`
  - `GitLabConnectionError`
  - `GitLabProjectNotFoundError`
  - `GitLabAccessDeniedError`
  - `MRNotFoundError`
  - `FileNotFoundInMRError`
  - `DiscussionNotFoundError`
  - `EmptyCommentError`

- [x] ステップ3: `glreview/services/cache.py` の生成
  - `LRUCache[K, V]` — ジェネリックLRUキャッシュ
  - `collections.OrderedDict` ベースの実装
  - エントリ数上限付き（コンストラクタで指定）
  - `get(key)` / `set(key, value)` / `delete(key)` / `clear()` メソッド
  - スレッドセーフは不要（asyncioシングルスレッド）

### GitLabClient

- [x] ステップ4: `glreview/services/gitlab_client.py` の生成
  - `GitLabClient` クラス
  - `__init__(self, config: AppConfig)`: python-gitlab の `Gitlab` インスタンス生成（timeout=(10, 30)）
  - `async connect(self)`: `asyncio.to_thread` で `gl.auth()` を呼び出し、認証検証
  - `async get_project(self, project_path: str)`: プロジェクト取得
  - `async get_current_user(self)`: 現在のユーザー取得（id, username）
  - `_wrap_api_error(self, exc)`: python-gitlab例外 → 内部エラー変換プライベートメソッド
  - SECURITY-03準拠: ログにトークン非出力
  - SECURITY-09準拠: ユーザー向けメッセージに内部詳細非包含

### MRService

- [x] ステップ5: `glreview/services/mr_service.py` の生成
  - `MRService` クラス
  - `__init__(self, client: GitLabClient, project_path: str)`: プロジェクト取得・ユーザー情報取得を非同期で準備
  - カテゴリ別MR一覧取得（遅延読み込み、per_page=20）:
    - `async get_assigned_to_me(self, page: int = 1) -> PaginatedResult`
    - `async get_created_by_me(self, page: int = 1) -> PaginatedResult`
    - `async get_unassigned(self, page: int = 1) -> PaginatedResult`
    - `async get_assigned_to_others(self, page: int = 1) -> PaginatedResult`
      （assignee_id="Any" で取得後、自ユーザーを除外）
  - 詳細・変更・差分:
    - `async get_mr_detail(self, mr_iid: int) -> MergeRequestDetail` （キャッシュ対象）
    - `async get_mr_changes(self, mr_iid: int) -> list[FileChange]` （キャッシュ対象）
    - `async get_mr_diff(self, mr_iid: int, file_path: str) -> FileDiff` （キャッシュ対象）
  - `async load(self)`: プロジェクト・ユーザー情報の非同期初期化
  - `invalidate_cache(self, mr_iid: int | None = None)`: キャッシュ無効化（Noneで全クリア）
  - `_convert_to_summary`, `_convert_to_detail`: 変換プライベートメソッド
  - ソート順: `AppConfig.sort_order`（デフォルト: "updated_at"）
  - LRUキャッシュ: MR詳細100件、変更ファイル100件、差分50件
  - 並行取得のための `asyncio.gather` 使用

- [x] ステップ6: `PaginatedResult` と `MRCategory` の `glreview/services/types.py` への追加
  - `PaginatedResult` dataclass（items, has_next_page, next_page）
  - `MRCategory` Enum（ASSIGNED_TO_ME, CREATED_BY_ME, UNASSIGNED, ASSIGNED_TO_OTHERS）

### CommentService

- [x] ステップ7: `glreview/services/comment_service.py` の生成
  - `CommentService` クラス
  - `__init__(self, client: GitLabClient, project_path: str)`
  - `async get_discussions(self, mr_iid: int) -> list[Discussion]`:
    - システムノート（`note.system == True`）を除外
    - LRUキャッシュ100件
  - `async add_inline_comment(self, mr_iid: int, file_path: str, line: int, body: str, line_type: str) -> Note`:
    - 本文空バリデーション → `EmptyCommentError`
    - MR差分のbase_sha/head_sha/start_sha取得
    - ディスカッション作成
    - 成功後にディスカッションキャッシュを無効化
  - `async add_note(self, mr_iid: int, body: str) -> Note`:
    - 本文空バリデーション → `EmptyCommentError`
    - ノート作成
    - 成功後にディスカッションキャッシュを無効化
  - `async reply_to_discussion(self, mr_iid: int, discussion_id: str, body: str) -> Note`:
    - 本文空バリデーション → `EmptyCommentError`
    - リプライ作成、ディスカッション未発見時 → `DiscussionNotFoundError`
    - 成功後にディスカッションキャッシュを無効化
  - `_convert_discussion`, `_convert_note`, `_convert_position`: 変換プライベートメソッド

### ユニットテスト

- [x] ステップ8: `glreview/services/tests/test_exceptions.py` の生成
  - 各例外クラスのインスタンス化テスト
  - 継承関係テスト（`GLReviewAPIError` 基底）

- [x] ステップ9: `glreview/services/tests/test_cache.py` の生成
  - LRUキャッシュのget/set/deleteテスト
  - エントリ数上限到達時のLRU破棄テスト
  - clearテスト

- [x] ステップ10: `glreview/services/tests/test_gitlab_client.py` の生成
  - `unittest.mock.MagicMock` でpython-gitlab `Gitlab` をモック
  - 認証成功・失敗テスト
  - プロジェクト取得成功・404・403テスト
  - `_wrap_api_error` の各例外変換テスト

- [x] ステップ11: `glreview/services/tests/test_mr_service.py` の生成
  - MRService全メソッドのモックテスト
  - 各カテゴリ取得のフィルタリングテスト（特に "assigned_to_others" の自ユーザー除外）
  - `_convert_to_summary` / `_convert_to_detail` 変換テスト（フィールドマッピング）
  - ページネーション（has_next_page）テスト
  - キャッシュヒット/ミス/無効化テスト
  - `FileNotFoundInMRError` テスト

- [x] ステップ12: `glreview/services/tests/test_comment_service.py` の生成
  - ディスカッション取得テスト（システムノート除外確認）
  - インラインコメント投稿テスト（NotePosition生成確認）
  - ノート投稿テスト
  - リプライ投稿テスト
  - `EmptyCommentError` テスト（空文字・空白のみ）
  - `DiscussionNotFoundError` テスト
  - コメント投稿後のキャッシュ無効化確認

- [x] ステップ13: `glreview/services/tests/test_mr_service_integration.py` の生成
  - `pytest.mark.integration` マーク付き
  - 実際のGitLabインスタンス接続テスト（環境変数 `LAZYGITLAB_TEST_TOKEN`, `LAZYGITLAB_TEST_URL`, `LAZYGITLAB_TEST_PROJECT` から設定）
  - 環境変数未設定時はスキップ
  - MR一覧取得・詳細取得・差分取得の疎通確認

### pyproject.toml 更新

- [x] ステップ14: `pyproject.toml` への依存追加
  - `python-gitlab` をランタイム依存に追加（バージョン固定）
  - `pytest-asyncio` をdev依存に追加（バージョン固定）
  - `asyncio_mode = "auto"` を `[tool.pytest.ini_options]` に追加

### ドキュメント

- [x] ステップ15: コードサマリードキュメント
  - `aidlc-docs/construction/gitlab-api-services/code/code-summary.md`
  - 生成ファイル一覧と各ファイルの概要
  - テストカバレッジ概要
  - UNIT-03への公開インターフェース説明
