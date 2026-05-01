# UNIT-03: TUI Application ドメインエンティティ

## 概要

UNIT-03で使用・管理するTUI固有のドメインエンティティを定義する。データモデル（UNIT-01）とAPIサービス（UNIT-02）に依存し、UI表示に特化した型を追加する。

---

## 1. UNIT-03 固有エンティティ

### 1.1 差分表示モード

```python
class DiffViewMode(Enum):
    """差分表示モード。"""
    UNIFIED = "unified"
    SIDE_BY_SIDE = "side_by_side"
```

### 1.2 ツリーノードデータ

ツリーの各ノードに付与するメタデータ。ノード選択時にどの操作を行うか判定する。

```python
class TreeNodeType(Enum):
    """ツリーノードの種別。"""
    CATEGORY = "category"       # カテゴリ（Assigned to me, etc.）
    MR = "mr"                   # MRノード
    OVERVIEW = "overview"       # Overview選択肢
    FILE = "file"               # 変更ファイル
    LOAD_MORE = "load_more"     # 追加読み込み

@dataclass
class TreeNodeData:
    """ツリーノードに紐づくデータ。"""
    node_type: TreeNodeType
    mr_iid: int | None = None           # MR/Overview/File ノード用
    file_path: str | None = None        # File ノード用
    category: MRCategory | None = None  # Category ノード用
    next_page: int | None = None        # Load more ノード用
```

### 1.3 コンテンツ表示状態

```python
class ContentViewState(Enum):
    """右ペインの表示状態。"""
    EMPTY = "empty"             # 初期状態（何も選択されていない）
    OVERVIEW = "overview"       # MR Overviewを表示中
    DIFF = "diff"               # ファイル差分を表示中
    LOADING = "loading"         # データ読み込み中
    ERROR = "error"             # エラー表示中
```

---

## 2. コンポーネント間の依存関係

```
UNIT-01 (Infrastructure)
  |
  +-- AppConfig → GLReviewApp（設定値取得）
  +-- ConfigManager → GLReviewApp（エディタ設定）
  +-- GitRepoDetector → GLReviewApp（プロジェクト検出）
  +-- get_logger → 全コンポーネント（ロギング）

UNIT-02 (GitLab API Services)
  |
  +-- GitLabClient → GLReviewApp（接続管理）
  +-- MRService → MRListPanel, ContentPanel（MRデータ取得）
  +-- CommentService → ContentPanel, CommentDialog（コメント操作）
  +-- PaginatedResult → MRListPanel（遅延読み込み）
  +-- MRCategory → MRListPanel（カテゴリ分類）
  +-- GLReviewAPIError → エラーダイアログ（エラーメッセージ取得）

UNIT-01 データモデル
  |
  +-- MergeRequestSummary → MRListPanel（一覧表示）
  +-- MergeRequestDetail → ContentPanel（Overview表示）
  +-- FileChange → MRListPanel（変更ファイルノード）
  +-- FileDiff → ContentPanel（差分表示）
  +-- Discussion, Note → ContentPanel（ディスカッション表示）
  +-- CommentType, CommentContext → CommentDialog（コメント操作）
```

---

## 3. Textualウィジェット継承関係

```
textual.app.App
  └── GLReviewApp

textual.widget.Widget
  ├── MRListPanel（内部にTree[TreeNodeData]を含む）
  └── ContentPanel（内部にRichLogまたはカスタムウィジェット）

textual.screen.ModalScreen
  ├── CommentDialog
  ├── HelpScreen
  └── ErrorDialog（エラー表示用モーダル）
```
