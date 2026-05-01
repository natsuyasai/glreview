# コンポーネントメソッドシグネチャ

## TUI層

### App

```python
class GLReviewApp(textual.app.App):
    def __init__(self, mr_id: int | None = None) -> None: ...
    def compose(self) -> ComposeResult: ...
    def on_mount(self) -> None: ...
    def action_show_help(self) -> None: ...
    def action_quit(self) -> None: ...
    def action_refresh(self) -> None: ...
    def action_open_in_editor(self) -> None: ...
```

### MRListPanel

```python
class MRListPanel(textual.widget.Widget):
    def on_mount(self) -> None: ...
    async def load_merge_requests(self) -> None: ...
    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None: ...
    def expand_mr(self, mr_id: int) -> None: ...
    def refresh_list(self) -> None: ...
```

### ContentPanel

```python
class ContentPanel(textual.widget.Widget):
    async def show_overview(self, mr_id: int) -> None: ...
    async def show_diff(self, mr_id: int, file_path: str) -> None: ...
    def get_selected_line(self) -> tuple[str, int] | None: ...
    def action_add_comment(self) -> None: ...
    def highlight_existing_comments(self, comments: list[Comment]) -> None: ...
```

### CommentDialog

```python
class CommentDialog(textual.screen.ModalScreen):
    def __init__(self, comment_type: CommentType, context: CommentContext) -> None: ...
    def compose(self) -> ComposeResult: ...
    async def action_submit(self) -> None: ...
    def action_cancel(self) -> None: ...
```

### HelpScreen

```python
class HelpScreen(textual.screen.ModalScreen):
    def compose(self) -> ComposeResult: ...
    def action_close(self) -> None: ...
```

## API層

### GitLabClient

```python
class GitLabClient:
    def __init__(self, config: AppConfig) -> None: ...
    def connect(self) -> None: ...
    def get_project(self, project_path: str) -> gitlab.v4.objects.Project: ...
    def get_current_user(self) -> gitlab.v4.objects.CurrentUser: ...
```

### MRService

```python
class MRService:
    def __init__(self, client: GitLabClient, project_path: str) -> None: ...
    def get_assigned_to_me(self) -> list[MergeRequestSummary]: ...
    def get_created_by_me(self) -> list[MergeRequestSummary]: ...
    def get_unassigned(self) -> list[MergeRequestSummary]: ...
    def get_assigned_to_others(self) -> list[MergeRequestSummary]: ...
    def get_mr_detail(self, mr_iid: int) -> MergeRequestDetail: ...
    def get_mr_changes(self, mr_iid: int) -> list[FileChange]: ...
    def get_mr_diff(self, mr_iid: int, file_path: str) -> FileDiff: ...
```

### CommentService

```python
class CommentService:
    def __init__(self, client: GitLabClient, project_path: str) -> None: ...
    def get_discussions(self, mr_iid: int) -> list[Discussion]: ...
    def add_inline_comment(self, mr_iid: int, file_path: str, line: int, body: str, line_type: str) -> Note: ...
    def add_note(self, mr_iid: int, body: str) -> Note: ...
    def reply_to_discussion(self, mr_iid: int, discussion_id: str, body: str) -> Note: ...
```

## 基盤層

### ConfigManager

```python
class ConfigManager:
    def __init__(self, config_path: Path | None = None) -> None: ...
    def load(self) -> AppConfig: ...
    def create_default_config(self) -> None: ...
    def validate(self, config: AppConfig) -> list[str]: ...
```

### GitRepoDetector

```python
class GitRepoDetector:
    def __init__(self, working_dir: Path | None = None) -> None: ...
    def detect_remote_url(self) -> str: ...
    def parse_gitlab_info(self, remote_url: str) -> GitLabProjectInfo: ...
    def get_project_path(self) -> str: ...
```

### Logger

```python
def setup_logging(config: AppConfig) -> logging.Logger: ...
def get_logger(name: str) -> logging.Logger: ...
```

## データモデル（型定義）

```python
@dataclass
class AppConfig:
    gitlab_url: str
    token: str
    editor: str  # デフォルト: $EDITOR
    log_level: str
    theme: str

@dataclass
class GitLabProjectInfo:
    host: str
    project_path: str

@dataclass
class MergeRequestSummary:
    iid: int
    title: str
    author: str
    assignee: str | None
    status: str
    labels: list[str]
    updated_at: str

@dataclass
class MergeRequestDetail:
    iid: int
    title: str
    description: str
    author: str
    assignee: str | None
    status: str
    labels: list[str]
    milestone: str | None
    pipeline_status: str | None
    web_url: str
    created_at: str
    updated_at: str

@dataclass
class FileChange:
    old_path: str
    new_path: str
    new_file: bool
    deleted_file: bool
    renamed_file: bool

@dataclass
class FileDiff:
    file_path: str
    diff: str
    old_path: str
    new_path: str

class CommentType(enum.Enum):
    INLINE = "inline"
    NOTE = "note"
    REPLY = "reply"

@dataclass
class CommentContext:
    mr_iid: int
    file_path: str | None  # インラインコメント時
    line: int | None        # インラインコメント時
    line_type: str | None   # "new" or "old"
    discussion_id: str | None  # リプライ時

@dataclass
class Discussion:
    id: str
    notes: list[Note]

@dataclass
class Note:
    id: int
    author: str
    body: str
    created_at: str
    position: NotePosition | None  # インラインコメントの場合

@dataclass
class NotePosition:
    file_path: str
    new_line: int | None
    old_line: int | None
```
