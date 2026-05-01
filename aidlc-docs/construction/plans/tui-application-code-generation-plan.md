# UNIT-03: TUI Application コード生成計画

## ユニットコンテキスト

- **ユニット**: UNIT-03 TUI Application（UI層）
- **プロジェクトタイプ**: グリーンフィールド（モノリス）
- **ワークスペースルート**: `c:\Users\fuku\Desktop\glreview`
- **コード配置**: `glreview/tui/`、エントリポイント更新: `glreview/__main__.py`

## 依存関係

- **UNIT-01依存**: `AppConfig`（ConfigManager経由）、全データモデル（`glreview/models.py`）、`get_logger`
- **UNIT-02依存**: `GitLabClient`, `MRService`, `CommentService`, `PaginatedResult`, `MRCategory`, エラークラス群
- **外部依存**: `textual>=0.60,<1.0`, `pygments>=2.17,<3.0`（pyproject.tomlに記載済み）
- **テスト依存**: `pytest`（既存）、`pytest-asyncio`（既存）、`textual.testing`（textualに内包）

## 対応要件

- FR-01（MR一覧表示）
- FR-02（MR詳細表示・サイドバートグル）
- FR-03（Overview表示）
- FR-04（差分表示・シンタックスハイライト・外部エディタ連携）
- FR-04a（外部エディタで開く）
- FR-05（コメント機能 — UI操作部分）
- NFR-TUI-PERF-03（仮想スクロール）
- NFR-TUI-UX-02（ステータスバーローディング）
- NFR-TUI-REL-01/02/03（エラーハンドリング）

## パッケージ構造

```
glreview/
  tui/
    __init__.py
    app.py              # GLReviewApp (App)
    entities.py         # DiffViewMode, TreeNodeType, TreeNodeData, ContentViewState
    messages.py         # ShowOverview, ShowDiff (Textual Messages)
    styles.tcss         # Textual CSS
    widgets/
      __init__.py
      mr_list_panel.py  # MRListPanel (左ペイン)
      content_panel.py  # ContentPanel (右ペイン)
    screens/
      __init__.py
      comment_dialog.py # CommentDialog (ModalScreen)
      help_screen.py    # HelpScreen (ModalScreen)
      error_dialog.py   # ErrorDialog (ModalScreen)
    tests/
      __init__.py
      test_entities.py         # エンティティ・ロジックテスト
      test_pilot.py            # Textual Pilotテスト（基本ケース）
```

---

## 生成ステップ

### パッケージ初期化

- [x] ステップ1: TUIパッケージ初期化
  - `glreview/tui/__init__.py` — 公開API定義（GLReviewApp）
  - `glreview/tui/widgets/__init__.py` — MRListPanel, ContentPanel
  - `glreview/tui/screens/__init__.py` — CommentDialog, HelpScreen, ErrorDialog
  - `glreview/tui/tests/__init__.py` — テストパッケージ

### ドメインエンティティ・メッセージ

- [x] ステップ2: `glreview/tui/entities.py` の生成
  - `DiffViewMode(Enum)` — UNIFIED / SIDE_BY_SIDE
  - `TreeNodeType(Enum)` — CATEGORY / MR / OVERVIEW / FILE / LOAD_MORE
  - `TreeNodeData(dataclass)` — node_type, mr_iid, file_path, category, next_page
  - `ContentViewState(Enum)` — EMPTY / OVERVIEW / DIFF / LOADING / ERROR

- [x] ステップ3: `glreview/tui/messages.py` の生成
  - `ShowOverview(Message)` — mr_iid: int
  - `ShowDiff(Message)` — mr_iid: int, file_path: str

### Textual CSS

- [x] ステップ4: `glreview/tui/styles.tcss` の生成
  - メインレイアウト（#main-container）
  - MRListPanel スタイル（width: 30%, hidden クラス）
  - ContentPanel スタイル（width: 1fr）
  - 差分表示カラー（.diff-add, .diff-remove, .diff-hunk, .diff-selected-line）
  - インラインコメントマーカー（.comment-marker）

### モーダルスクリーン

- [x] ステップ5: `glreview/tui/screens/error_dialog.py` の生成
  - `ErrorDialog(ModalScreen)` — エラーメッセージ表示
  - Props: `error_message: str`
  - OKボタン（Enterキー / クリック）でダイアログを閉じる
  - CSS: width 60%, height auto, background $error

- [x] ステップ6: `glreview/tui/screens/help_screen.py` の生成
  - `HelpScreen(ModalScreen)` — キーバインド一覧表示
  - 静的コンテンツ（DataTableでキーバインド一覧）
  - Escキーで閉じる
  - Global / Navigation / Diff View / Comment Input セクション

- [x] ステップ7: `glreview/tui/screens/comment_dialog.py` の生成
  - `CommentDialog(ModalScreen)` — コメント入力ダイアログ
  - Props: `comment_context: CommentContext`, `comment_service: CommentService`, `editor_command: str`
  - `submitting: bool` 状態
  - TextArea + ボタン群（Submit Ctrl+S, External Editor Ctrl+E, Cancel Escape）
  - 外部エディタ連携: `app.suspend()` + subprocess + tmpファイル
  - バリデーション（空文字禁止）
  - 送信成功後: 親へ通知してダイアログを閉じる

### ウィジェット

- [x] ステップ8: `glreview/tui/widgets/mr_list_panel.py` の生成
  - `MRListPanel(Widget)` — 左ペイン
  - Props: `mr_service: MRService`
  - `category_pages: dict[MRCategory, int]` / `selected_mr_iid: int | None` / `expanded_mrs: set[int]`
  - `on_mount`: 4カテゴリツリーをロード（asyncio.gather）
  - ツリーノード操作:
    - カテゴリノード → 展開/折りたたみ
    - MRノード未展開 → `expand_mr(iid)`: ファイル一覧取得 + 子ノード追加
    - Overviewノード → `post_message(ShowOverview(iid))`
    - ファイルノード → `post_message(ShowDiff(iid, file_path))`
    - Load moreノード → 次ページ取得 + ノード追加
  - ステータスバーにローディングインジケーター表示
  - エラー時はErrorDialogを push

- [x] ステップ9: `glreview/tui/widgets/content_panel.py` の生成
  - `ContentPanel(Widget)` — 右ペイン
  - Props: `mr_service: MRService`, `comment_service: CommentService`
  - 状態: `view_state`, `diff_mode`, `current_mr_iid`, `current_file_path`, `selected_line`, `selected_line_type`
  - `on_show_overview`: MR詳細 + ディスカッション取得 → マークダウン風テキスト描画
  - `on_show_diff`: 差分取得 → Pygmentsハイライト + インラインコメントマーカー描画
  - `t` キー: `diff_mode` 切替 → 再描画
  - `c` キー（差分時）: 選択行情報取得 → `CommentDialog` push（INLINE）
  - `c` キー（Overview時）: `CommentDialog` push（NOTE）
  - ローディング中はステータスバーにインジケーター表示
  - RichLog を使った仮想スクロール対応差分表示

### メインアプリ

- [x] ステップ10: `glreview/tui/app.py` の生成
  - `GLReviewApp(App)` — メインアプリクラス
  - Props: `config: AppConfig`, `initial_mr_id: int | None`
  - 初期化: `GitLabClient` 作成 → `MRService` / `CommentService` 初期化
  - `on_mount`: 接続 → エラー時 ErrorDialog
  - `sidebar_visible: bool` リアクティブ属性
  - BINDINGS: q(終了), ?(ヘルプ), r(リフレッシュ), e(エディタ), [(サイドバートグル)
  - `action_quit` / `action_show_help` / `action_refresh` / `action_open_in_editor` / `action_toggle_sidebar`
  - `CSS_PATH` で styles.tcss 参照
  - `initial_mr_id` が指定された場合は `on_mount` で自動選択

- [x] ステップ11: `glreview/__main__.py` の更新
  - インポートパスを `glreview.tui.app` に修正
  - `GLReviewApp(config=config, initial_mr_id=args.mr_id)` の呼び出し

### テスト

- [x] ステップ12: `glreview/tui/tests/test_entities.py` の生成
  - `TreeNodeData` のデフォルト値テスト
  - `TreeNodeType` 全値テスト
  - `ContentViewState` 全値テスト
  - `DiffViewMode` トグルロジックテスト

- [x] ステップ13: `glreview/tui/tests/test_pilot.py` の生成
  - `textual.testing` を使ったヘッドレステスト
  - アプリの起動・終了テスト（MRService/CommentService をモック）
  - `[` キーによるサイドバートグルテスト
  - `?` キーによるヘルプ表示テスト
  - `q` キーによる終了テスト
  - ErrorDialog の表示・OKボタン確認テスト

### ドキュメント

- [x] ステップ14: コードサマリードキュメント
  - `aidlc-docs/construction/tui-application/code/code-summary.md`
  - 生成ファイル一覧と各ファイルの概要
  - テストカバレッジ概要
  - アプリケーション起動フロー
