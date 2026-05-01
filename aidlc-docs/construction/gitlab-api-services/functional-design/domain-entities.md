# UNIT-02: GitLab API Services ドメインエンティティ

## 概要

UNIT-02で使用・管理するドメインエンティティと、python-gitlabオブジェクトからの変換ルールを定義する。データモデル自体はUNIT-01で定義��み（`glreview/models.py`）であるため、ここではAPI層固有のエンティティ関係と変換ロジックに焦点を当てる。

---

## 1. エンティティ関係図

```
GitLabClient
  |
  +-- manages --> Gitlab (python-gitlab)
  |                |
  |                +-- resolves --> Project
  |                +-- provides --> CurrentUser
  |
  +-- used by --> MRService
  +-- used by --> CommentService

MRService
  |
  +-- produces --> MergeRequestSummary (一覧)
  +-- produces --> MergeRequestDetail (詳細)
  +-- produces --> FileChange (変更ファイル一覧)
  +-- produces --> FileDiff (ファイル差分)

CommentService
  |
  +-- produces --> Discussion (ディスカッション一覧)
  +-- produces --> Note (個別コメント)
  +-- uses --> NotePosition (インラインコメント位置)
```

---

## 2. UNIT-02 固有エンティティ

### 2.1 APIエラー型

UNIT-02で定義するカスタム例外クラス。すべて共通基底クラスを継承する。

```python
class GLReviewAPIError(Exception):
    """API層の基底エラー。"""
    message: str  # ユーザー向けメッセージ（内部詳細を含まない）

class GitLabAuthError(GLReviewAPIError):
    """認証失敗。"""

class GitLabConnectionError(GLReviewAPIError):
    """接続失敗・タイムアウト。"""

class GitLabProjectNotFoundError(GLReviewAPIError):
    """プロジェクトが見つからない。"""

class GitLabAccessDeniedError(GLReviewAPIError):
    """アクセス権限がない。"""

class MRNotFoundError(GLReviewAPIError):
    """MRが見つからない。"""

class FileNotFoundInMRError(GLReviewAPIError):
    """MR内にファイルが見つからない。"""

class DiscussionNotFoundError(GLReviewAPIError):
    """ディスカッションが見つからない。"""

class EmptyCommentError(GLReviewAPIError):
    """コメント本文が空。"""
```

### 2.2 ページネーション結果型

MR一覧の遅延読み込みを管理するための型。

```python
@dataclass
class PaginatedResult:
    """ページネーション付きMR一覧の結果。"""
    items: list[MergeRequestSummary]
    has_next_page: bool
    next_page: int | None  # 次ページ番号（has_next_page=Falseの場合はNone）
```

### 2.3 MRカテゴリ列挙型

MR一覧のカテゴリを明示的に型で管理する。

```python
class MRCategory(Enum):
    """MR一覧のカテゴリ分類。"""
    ASSIGNED_TO_ME = "assigned_to_me"
    CREATED_BY_ME = "created_by_me"
    UNASSIGNED = "unassigned"
    ASSIGNED_TO_OTHERS = "assigned_to_others"
```

---

## 3. python-gitlab オブジェクト → 内部モデル変換ルール

### 3.1 MergeRequest → MergeRequestSummary

| python-gitlab属性 | 内部モデルフィールド | 変換ルール |
|---|---|---|
| `mr.iid` | `iid` | そのまま (int) |
| `mr.title` | `title` | そのまま (str) |
| `mr.author["username"]` | `author` | dictからusernameを抽出 |
| `mr.assignee` | `assignee` | `mr.assignee["username"]` if assignee else None |
| `mr.state` | `status` | そのまま (str) |
| `mr.labels` | `labels` | そのまま (list[str]) |
| `mr.updated_at` | `updated_at` | そのまま (str, ISO 8601形式) |

### 3.2 MergeRequest → MergeRequestDetail

| python-gitlab属性 | 内部モデルフィールド | 変換ルール |
|---|---|---|
| `mr.iid` | `iid` | そのまま |
| `mr.title` | `title` | そのまま |
| `mr.description` | `description` | そのまま（Noneの場合は空文字列） |
| `mr.author["username"]` | `author` | dictからusernameを抽出 |
| `mr.assignee` | `assignee` | username or None |
| `mr.state` | `status` | そのまま |
| `mr.labels` | `labels` | そのまま |
| `mr.milestone` | `milestone` | `mr.milestone["title"]` if milestone else None |
| `mr.head_pipeline` | `pipeline_status` | `mr.head_pipeline["status"]` if head_pipeline else None |
| `mr.web_url` | `web_url` | そのまま |
| `mr.created_at` | `created_at` | そのまま |
| `mr.updated_at` | `updated_at` | そのまま |

### 3.3 MR Changes → FileChange

| python-gitlab属性 | 内部モデルフィールド | 変換ルール |
|---|---|---|
| `change["old_path"]` | `old_path` | そのまま |
| `change["new_path"]` | `new_path` | そのまま |
| `change["new_file"]` | `new_file` | そのまま (bool) |
| `change["deleted_file"]` | `deleted_file` | その���ま (bool) |
| `change["renamed_file"]` | `renamed_file` | そのまま (bool) |

### 3.4 MR Diff → FileDiff

| python-gitlab属性 | 内部モデルフィールド | 変換ルール |
|---|---|---|
| `change["new_path"]` | `file_path` | new_pathを使用 |
| `change["diff"]` | `diff` | そのまま (unified diff文字列) |
| `change["old_path"]` | `old_path` | そのまま |
| `change["new_path"]` | `new_path` | そのまま |

### 3.5 Discussion → Discussion / Note / NotePosition

| python-gitlab属性 | 内部モデルフィールド | 変換ルール |
|---|---|---|
| `discussion.id` | `Discussion.id` | そのまま |
| `discussion.attributes["notes"]` | `Discussion.notes` | 各noteをNote変換（system=True除外） |
| `note["id"]` | `Note.id` | そのまま |
| `note["author"]["username"]` | `Note.author` | dictから抽出 |
| `note["body"]` | `Note.body` | そのまま |
| `note["created_at"]` | `Note.created_at` | そのまま |
| `note["position"]` | `Note.position` | positionがある場合のみNotePosition変換 |
| `position["new_path"]` | `NotePosition.file_path` | new_pathを使用 |
| `position["new_line"]` | `NotePosition.new_line` | そのまま (int or None) |
| `position["old_line"]` | `NotePosition.old_line` | そのまま (int or None) |

---

## 4. コンポーネント間の依存関係

```
AppConfig (UNIT-01)
    |
    v
GitLabClient
    |
    +----> MRService
    |         |
    |         +-- uses --> MergeRequestSummary (UNIT-01 models)
    |         +-- uses --> MergeRequestDetail (UNIT-01 models)
    |         +-- uses --> FileChange (UNIT-01 models)
    |         +-- uses --> FileDiff (UNIT-01 models)
    |         +-- uses --> PaginatedResult (UNIT-02 固有)
    |         +-- uses --> MRCategory (UNIT-02 固有)
    |
    +----> CommentService
              |
              +-- uses --> Discussion (UNIT-01 models)
              +-- uses --> Note (UNIT-01 models)
              +-- uses --> NotePosition (UNIT-01 models)
```

### 依存方向の制約

- UNIT-02はUNIT-01のデータモデルとConfigManagerに依存する（下流依存）
- UNIT-02はUNIT-03（TUI層）に依存しない（上流には依存しない）
- UNIT-02内のコンポーネント依存: MRService → GitLabClient, CommentService → GitLabClient
