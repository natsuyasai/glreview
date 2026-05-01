"""glreview.models のユニットテスト。"""

from __future__ import annotations

import pytest

from glreview.models import (
    AppConfig,
    CommentContext,
    CommentType,
    Discussion,
    FileChange,
    FileDiff,
    GitLabProjectInfo,
    MergeRequestDetail,
    MergeRequestSummary,
    Note,
    NotePosition,
)


class TestAppConfig:
    def test_基本的なインスタンスを作成できる(self):
        cfg = AppConfig(gitlab_url="https://gitlab.com", token="glpat-abc")
        assert cfg.gitlab_url == "https://gitlab.com"
        assert cfg.token == "glpat-abc"

    def test_デフォルト値が正しい(self):
        cfg = AppConfig(gitlab_url="https://gitlab.com", token="t")
        assert cfg.editor == "vi"
        assert cfg.log_level == "INFO"
        assert cfg.theme == "dark"
        assert cfg.remote_name == ""

    def test_URLの末尾スラッシュが除去される(self):
        cfg = AppConfig(gitlab_url="https://gitlab.com/", token="t")
        assert cfg.gitlab_url == "https://gitlab.com"

    def test_URLの複数の末尾スラッシュが除去される(self):
        cfg = AppConfig(gitlab_url="https://gitlab.example.com///", token="t")
        assert cfg.gitlab_url == "https://gitlab.example.com"


class TestGitLabProjectInfo:
    def test_基本的なインスタンスを作成できる(self):
        info = GitLabProjectInfo(host="gitlab.com", project_path="group/project")
        assert info.host == "gitlab.com"
        assert info.project_path == "group/project"

    def test_hostが空の場合にValueErrorが発生する(self):
        with pytest.raises(ValueError, match="host"):
            GitLabProjectInfo(host="", project_path="group/project")

    def test_project_pathが空の場合にValueErrorが発生する(self):
        with pytest.raises(ValueError, match="project_path"):
            GitLabProjectInfo(host="gitlab.com", project_path="")

    def test_サブグループパスをサポートする(self):
        info = GitLabProjectInfo(host="gitlab.com", project_path="group/sub1/sub2/project")
        assert info.project_path == "group/sub1/sub2/project"


class TestMergeRequestSummary:
    def test_基本的なMRサマリーを作成できる(self):
        mr = MergeRequestSummary(
            iid=1,
            title="Fix bug",
            author="alice",
            status="opened",
            labels=["bug"],
            updated_at="2024-01-01T00:00:00Z",
        )
        assert mr.iid == 1
        assert mr.assignee is None

    def test_担当者を指定してMRサマリーを作成できる(self):
        mr = MergeRequestSummary(
            iid=2,
            title="Add feature",
            author="bob",
            status="opened",
            labels=[],
            updated_at="2024-01-01T00:00:00Z",
            assignee="alice",
        )
        assert mr.assignee == "alice"


class TestMergeRequestDetail:
    def test_基本的なMR詳細情報を作成できる(self):
        mr = MergeRequestDetail(
            iid=1,
            title="Fix bug",
            description="",
            author="alice",
            status="opened",
            labels=[],
            web_url="https://gitlab.com/g/p/-/merge_requests/1",
            created_at="2024-01-01T00:00:00Z",
            updated_at="2024-01-02T00:00:00Z",
        )
        assert mr.milestone is None
        assert mr.pipeline_status is None


class TestFileChange:
    def test_基本的なファイル変更情報を作成できる(self):
        fc = FileChange(
            old_path="a.py",
            new_path="a.py",
            new_file=False,
            deleted_file=False,
            renamed_file=False,
        )
        assert fc.old_path == "a.py"

    def test_リネームファイルで同一パスの場合ValueErrorが発生する(self):
        with pytest.raises(ValueError, match="renamed_file"):
            FileChange(
                old_path="a.py",
                new_path="a.py",
                new_file=False,
                deleted_file=False,
                renamed_file=True,
            )

    def test_リネームファイルで異なるパスは正常に作成できる(self):
        fc = FileChange(
            old_path="a.py",
            new_path="b.py",
            new_file=False,
            deleted_file=False,
            renamed_file=True,
        )
        assert fc.renamed_file is True


class TestFileDiff:
    def test_基本的なFileDiffを作成できる(self):
        fd = FileDiff(
            file_path="a.py",
            diff="@@ -1,1 +1,2 @@\n foo\n+bar",
            old_path="a.py",
            new_path="a.py",
        )
        assert fd.diff.startswith("@@")


class TestCommentType:
    def test_列挙値が正しい(self):
        assert CommentType.INLINE.value == "inline"
        assert CommentType.NOTE.value == "note"
        assert CommentType.REPLY.value == "reply"


class TestCommentContext:
    def test_有効なINLINEコメントを作成できる(self):
        ctx = CommentContext(
            mr_iid=1,
            comment_type=CommentType.INLINE,
            file_path="a.py",
            line=5,
            line_type="new",
        )
        assert ctx.file_path == "a.py"

    def test_INLINEコメントでfile_pathがない場合ValueErrorが発生する(self):
        with pytest.raises(ValueError, match="INLINE"):
            CommentContext(
                mr_iid=1,
                comment_type=CommentType.INLINE,
                line=5,
                line_type="new",
            )

    def test_有効なNOTEコメントを作成できる(self):
        ctx = CommentContext(mr_iid=1, comment_type=CommentType.NOTE)
        assert ctx.discussion_id is None

    def test_NOTEコメントでfile_pathがある場合ValueErrorが発生する(self):
        with pytest.raises(ValueError, match="NOTE"):
            CommentContext(
                mr_iid=1,
                comment_type=CommentType.NOTE,
                file_path="a.py",
            )

    def test_有効なREPLYコメントを作成できる(self):
        ctx = CommentContext(
            mr_iid=1,
            comment_type=CommentType.REPLY,
            discussion_id="abc123",
        )
        assert ctx.discussion_id == "abc123"

    def test_REPLYコメントでdiscussion_idがない場合ValueErrorが発生する(self):
        with pytest.raises(ValueError, match="REPLY"):
            CommentContext(mr_iid=1, comment_type=CommentType.REPLY)


class TestNotePosition:
    def test_new_lineのみで作成できる(self):
        pos = NotePosition(file_path="a.py", new_line=10)
        assert pos.new_line == 10
        assert pos.old_line is None

    def test_old_lineのみで作成できる(self):
        pos = NotePosition(file_path="a.py", old_line=5)
        assert pos.old_line == 5

    def test_両方がNoneの場合ValueErrorが発生する(self):
        with pytest.raises(ValueError, match="least one"):
            NotePosition(file_path="a.py")


class TestNote:
    def test_基本的なノートを作成できる(self):
        note = Note(id=1, author="alice", body="LGTM", created_at="2024-01-01T00:00:00Z")
        assert note.position is None

    def test_位置情報付きのノートを作成できる(self):
        pos = NotePosition(file_path="a.py", new_line=3)
        note = Note(
            id=2,
            author="bob",
            body="Comment",
            created_at="2024-01-01T00:00:00Z",
            position=pos,
        )
        assert note.position.new_line == 3


class TestDiscussion:
    def test_基本的なディスカッションを作成できる(self):
        note = Note(id=1, author="alice", body="Hi", created_at="2024-01-01T00:00:00Z")
        disc = Discussion(id="disc1", notes=[note])
        assert disc.id == "disc1"
        assert len(disc.notes) == 1

    def test_ノートが空の場合ValueErrorが発生する(self):
        with pytest.raises(ValueError, match="least one note"):
            Discussion(id="disc1", notes=[])
