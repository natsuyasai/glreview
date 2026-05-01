"""glreview の共有データモデル。"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


@dataclass
class AppConfig:
    """config.toml から読み込むアプリケーション設定。"""

    gitlab_url: str
    token: str
    editor: str = "vi"
    terminal: str = ""
    log_level: str = "INFO"
    theme: str = "dark"
    remote_name: str = ""
    ssl_verify: bool = True
    pygments_style: str = ""

    def __post_init__(self) -> None:
        # 正規化: URLの末尾スラッシュを除去する
        self.gitlab_url = self.gitlab_url.rstrip("/")


@dataclass
class GitLabProjectInfo:
    """gitリモートURLから解析したGitLab接続情報。"""

    host: str
    project_path: str

    def __post_init__(self) -> None:
        if not self.host:
            raise ValueError("host must not be empty")
        if not self.project_path:
            raise ValueError("project_path must not be empty")


@dataclass
class MergeRequestSummary:
    """一覧表示用の軽量MR情報。"""

    iid: int
    title: str
    author: str
    status: str
    labels: list[str]
    updated_at: str
    assignee: str | None = None


@dataclass
class MergeRequestDetail:
    """概要表示用の完全なMR情報。"""

    iid: int
    title: str
    description: str
    author: str
    status: str
    labels: list[str]
    web_url: str
    created_at: str
    updated_at: str
    assignee: str | None = None
    milestone: str | None = None
    pipeline_status: str | None = None
    source_branch: str = ""


@dataclass
class FileChange:
    """マージリクエストで変更されたファイルのメタデータ。"""

    old_path: str
    new_path: str
    new_file: bool
    deleted_file: bool
    renamed_file: bool

    def __post_init__(self) -> None:
        if self.renamed_file and self.old_path == self.new_path:
            raise ValueError("renamed_file is True but old_path == new_path")


@dataclass
class FileDiff:
    """ファイルのdiff内容(unified diff形式)。"""

    file_path: str
    diff: str
    old_path: str
    new_path: str


class CommentType(Enum):
    """投稿するコメントの種別。"""

    INLINE = "inline"
    NOTE = "note"
    REPLY = "reply"


@dataclass
class CommentContext:
    """コメント投稿時に必要なコンテキスト。"""

    mr_iid: int
    comment_type: CommentType
    file_path: str | None = None
    line: int | None = None
    line_type: str | None = None  # "new" または "old"
    old_line: int | None = None  # ctx行のみ: old側の行番号
    discussion_id: str | None = None

    def __post_init__(self) -> None:
        if self.comment_type == CommentType.INLINE:
            if self.file_path is None or self.line is None or self.line_type is None:
                raise ValueError("INLINE comment requires file_path, line, and line_type")
        elif self.comment_type == CommentType.NOTE:
            if any(
                v is not None
                for v in (self.file_path, self.line, self.line_type, self.discussion_id)
            ):
                raise ValueError(
                    "NOTE comment must have file_path, line, line_type, and discussion_id as None"
                )
        elif self.comment_type == CommentType.REPLY:
            if self.discussion_id is None:
                raise ValueError("REPLY comment requires discussion_id")


@dataclass
class NotePosition:
    """ファイル内のインラインコメントの位置情報。"""

    file_path: str
    new_line: int | None = None
    old_line: int | None = None

    def __post_init__(self) -> None:
        if self.new_line is None and self.old_line is None:
            raise ValueError("At least one of new_line or old_line must be set")


@dataclass
class Note:
    """ディスカッション内の個別コメント/ノート。"""

    id: int
    author: str
    body: str
    created_at: str
    position: NotePosition | None = None


@dataclass
class Discussion:
    """マージリクエスト内のディスカッションスレッド。"""

    id: str
    notes: list[Note] = field(default_factory=list)

    def __post_init__(self) -> None:
        if len(self.notes) < 1:
            raise ValueError("Discussion must contain at least one note")
