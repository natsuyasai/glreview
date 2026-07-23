"""glreview.services.comment_service のユニットテスト。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import gitlab.exceptions
import pytest

from glreview.models import AppConfig
from glreview.services.comment_service import CommentService
from glreview.services.exceptions import (
    EmptyCommentError,
    GitLabConnectionError,
    MRNotFoundError,
)
from glreview.services.gitlab_client import CurrentUser, GitLabClient


@pytest.fixture
def config() -> AppConfig:
    return AppConfig(gitlab_url="https://gitlab.example.com", token="glpat-test")


@pytest.fixture
def mock_client(config: AppConfig) -> MagicMock:
    client = MagicMock(spec=GitLabClient)
    client._config = config
    client.get_project = AsyncMock(return_value=MagicMock())
    client.get_current_user = AsyncMock(return_value=CurrentUser(id=1, username="me"))
    client._wrap_api_error = MagicMock(side_effect=lambda e: e)
    return client


@pytest.fixture
async def service(mock_client: MagicMock) -> CommentService:
    svc = CommentService(mock_client, "group/project")
    await svc.load()
    return svc


def _make_raw_discussion(
    discussion_id: str = "abc123",
    notes: list[dict] | None = None,
) -> MagicMock:
    raw = MagicMock()
    raw.id = discussion_id
    raw.attributes = {
        "notes": notes
        or [
            {
                "id": 1,
                "author": {"username": "alice"},
                "body": "Hello",
                "created_at": "2026-01-01T00:00:00Z",
                "system": False,
                "position": None,
            }
        ]
    }
    return raw


class TestGetDiscussions:
    async def test_returns_discussions(self, service: CommentService) -> None:
        raw = _make_raw_discussion()

        async def mock_to_thread(fn, *args, **kwargs):
            return fn(*args, **kwargs)

        service._project.mergerequests.get = MagicMock(return_value=MagicMock())
        service._project.mergerequests.get.return_value.discussions.list = MagicMock(
            return_value=[raw]
        )
        with patch("asyncio.to_thread", side_effect=mock_to_thread):
            result = await service.get_discussions(1)
        assert len(result) == 1
        assert result[0].id == "abc123"
        assert result[0].notes[0].author == "alice"

    async def test_excludes_system_notes(self, service: CommentService) -> None:
        raw = _make_raw_discussion(
            notes=[
                {
                    "id": 1,
                    "author": {"username": "gitlab"},
                    "body": "merged this MR",
                    "created_at": "2026-01-01T00:00:00Z",
                    "system": True,
                    "position": None,
                }
            ]
        )

        async def mock_to_thread(fn, *args, **kwargs):
            return fn(*args, **kwargs)

        service._project.mergerequests.get = MagicMock(return_value=MagicMock())
        service._project.mergerequests.get.return_value.discussions.list = MagicMock(
            return_value=[raw]
        )
        with patch("asyncio.to_thread", side_effect=mock_to_thread):
            result = await service.get_discussions(1)
        assert len(result) == 0

    async def test_cache_hit(self, service: CommentService) -> None:
        raw = _make_raw_discussion()

        async def mock_to_thread(fn, *args, **kwargs):
            return fn(*args, **kwargs)

        service._project.mergerequests.get = MagicMock(return_value=MagicMock())
        service._project.mergerequests.get.return_value.discussions.list = MagicMock(
            return_value=[raw]
        )
        with patch("asyncio.to_thread", side_effect=mock_to_thread):
            r1 = await service.get_discussions(1)
            r2 = await service.get_discussions(1)
        assert r1 is r2


class TestValidateBody:
    def test_empty_raises(self, service: CommentService) -> None:
        with pytest.raises(EmptyCommentError):
            service._validate_body("")

    def test_whitespace_only_raises(self, service: CommentService) -> None:
        with pytest.raises(EmptyCommentError):
            service._validate_body("   ")

    def test_valid_body(self, service: CommentService) -> None:
        service._validate_body("valid comment")  # 例外なし


class TestAddNote:
    async def test_empty_body_raises(self, service: CommentService) -> None:
        with pytest.raises(EmptyCommentError):
            await service.add_note(1, "")

    async def test_add_note_creates_draft(self, service: CommentService) -> None:
        mock_draft = MagicMock()
        mock_draft.attributes = {
            "id": 99,
            "note": "my note",
            "position": None,
        }
        mock_mr = MagicMock()
        mock_mr.draft_notes.create = MagicMock(return_value=mock_draft)

        async def mock_to_thread(fn, *args, **kwargs):
            return fn(*args, **kwargs)

        service._project.mergerequests.get = MagicMock(return_value=mock_mr)
        with patch("asyncio.to_thread", side_effect=mock_to_thread):
            note = await service.add_note(1, "my note")
        assert note.id == 99
        assert note.author == "me"
        assert note.is_draft is True
        mock_mr.draft_notes.create.assert_called_once_with({"note": "my note"})

    async def test_does_not_touch_discussions_cache(self, service: CommentService) -> None:
        """下書き追加は公開済みディスカッションキャッシュに影響しないこと。"""
        service._discussions_cache.set(1, [])  # キャッシュに仕込む
        mock_draft = MagicMock()
        mock_draft.attributes = {"id": 1, "note": "x", "position": None}
        mock_mr = MagicMock()
        mock_mr.draft_notes.create = MagicMock(return_value=mock_draft)

        async def mock_to_thread(fn, *args, **kwargs):
            return fn(*args, **kwargs)

        service._project.mergerequests.get = MagicMock(return_value=mock_mr)
        with patch("asyncio.to_thread", side_effect=mock_to_thread):
            await service.add_note(1, "x")
        assert service._discussions_cache.get(1) is not None


class TestReplyToDiscussion:
    async def test_empty_body_raises(self, service: CommentService) -> None:
        with pytest.raises(EmptyCommentError):
            await service.reply_to_discussion(1, "disc-id", "")

    async def test_reply_creates_draft(self, service: CommentService) -> None:
        mock_draft = MagicMock()
        mock_draft.attributes = {
            "id": 55,
            "note": "reply text",
            "position": None,
        }
        mock_mr = MagicMock()
        mock_mr.discussions.get = MagicMock(return_value=MagicMock())
        mock_mr.draft_notes.create = MagicMock(return_value=mock_draft)

        async def mock_to_thread(fn, *args, **kwargs):
            return fn(*args, **kwargs)

        service._project.mergerequests.get = MagicMock(return_value=mock_mr)
        with patch("asyncio.to_thread", side_effect=mock_to_thread):
            note = await service.reply_to_discussion(1, "disc-abc", "reply text")
        assert note.id == 55
        assert note.body == "reply text"
        assert note.is_draft is True
        mock_mr.draft_notes.create.assert_called_once_with(
            {"note": "reply text", "in_reply_to_discussion_id": "disc-abc"}
        )


class TestConvertPosition:
    def test_none_returns_none(self, service: CommentService) -> None:
        assert service._convert_position(None) is None

    def test_both_none_returns_none(self, service: CommentService) -> None:
        assert service._convert_position({"new_line": None, "old_line": None}) is None

    def test_new_line_set(self, service: CommentService) -> None:
        pos = service._convert_position({"new_path": "foo.py", "new_line": 10, "old_line": None})
        assert pos is not None
        assert pos.new_line == 10
        assert pos.old_line is None

    def test_old_line_set(self, service: CommentService) -> None:
        pos = service._convert_position({"new_path": "bar.py", "new_line": None, "old_line": 3})
        assert pos is not None
        assert pos.old_line == 3


class TestGenerateLineCode:
    """_generate_line_code のユニットテスト。"""

    def test_new_line_only(self) -> None:
        """追加行: old=0, new=<line> の形式になること。"""
        import hashlib

        from glreview.services.comment_service import _generate_line_code

        sha = hashlib.sha1(b"foo.py").hexdigest()  # noqa: S324
        assert _generate_line_code("foo.py", None, 5) == f"{sha}_0_5"

    def test_old_line_only(self) -> None:
        """削除行: old=<line>, new=0 の形式になること。"""
        import hashlib

        from glreview.services.comment_service import _generate_line_code

        sha = hashlib.sha1(b"bar.py").hexdigest()  # noqa: S324
        assert _generate_line_code("bar.py", 3, None) == f"{sha}_3_0"

    def test_context_line(self) -> None:
        """コンテキスト行: old=<old_line>, new=<new_line> の形式になること。"""
        import hashlib

        from glreview.services.comment_service import _generate_line_code

        sha = hashlib.sha1(b"baz.py").hexdigest()  # noqa: S324
        assert _generate_line_code("baz.py", 8, 10) == f"{sha}_8_10"


class TestAddInlineComment:
    async def test_empty_body_raises(self, service: CommentService) -> None:
        with pytest.raises(EmptyCommentError):
            await service.add_inline_comment(1, "foo.py", 5, "", "new")

    async def test_add_inline_comment_creates_draft(self, service: CommentService) -> None:
        mock_draft = MagicMock()
        mock_draft.attributes = {
            "id": 10,
            "note": "inline comment",
            "position": {"new_path": "foo.py", "new_line": 5, "old_line": None},
        }
        mock_mr = MagicMock()
        mock_mr.diff_refs = {"base_sha": "aaa", "head_sha": "bbb", "start_sha": "ccc"}
        mock_mr.draft_notes.create = MagicMock(return_value=mock_draft)

        async def mock_to_thread(fn, *args, **kwargs):
            return fn(*args, **kwargs)

        service._project.mergerequests.get = MagicMock(return_value=mock_mr)
        with patch("asyncio.to_thread", side_effect=mock_to_thread):
            note = await service.add_inline_comment(1, "foo.py", 5, "inline comment", "new")
        assert note.id == 10
        assert note.author == "me"
        assert note.is_draft is True

    async def test_add_inline_comment_old_line(self, service: CommentService) -> None:
        mock_draft = MagicMock()
        mock_draft.attributes = {
            "id": 11,
            "note": "old line comment",
            "position": {"new_path": "bar.py", "new_line": None, "old_line": 3},
        }
        mock_mr = MagicMock()
        mock_mr.diff_refs = {"base_sha": "a", "head_sha": "b", "start_sha": "c"}
        mock_mr.draft_notes.create = MagicMock(return_value=mock_draft)

        async def mock_to_thread(fn, *args, **kwargs):
            return fn(*args, **kwargs)

        service._project.mergerequests.get = MagicMock(return_value=mock_mr)
        with patch("asyncio.to_thread", side_effect=mock_to_thread):
            note = await service.add_inline_comment(1, "bar.py", 3, "old line comment", "old")
        assert note.id == 11
        assert note.is_draft is True

    async def test_404_raises_mr_not_found(self, service: CommentService) -> None:
        exc = gitlab.exceptions.GitlabGetError(response_code=404, error_message="Not Found")

        async def mock_to_thread(fn, *args, **kwargs):
            raise exc

        with patch("asyncio.to_thread", side_effect=mock_to_thread):
            with pytest.raises(MRNotFoundError):
                await service.add_inline_comment(999, "foo.py", 1, "body", "new")

    async def test_position_new_line_only_for_add_line(self, service: CommentService) -> None:
        """追加行(new)のとき、position に new_line のみ含まれ old_line・line_code は含まれないこと。

        GitLab API 仕様:
        - 追加行: position[new_line] のみ送る。old_line は送らない
        - line_code はクライアントから送らない（GitLab がサーバー側で生成する）
        ref: https://docs.gitlab.com/api/discussions/
        """
        mock_draft = MagicMock()
        mock_draft.attributes = {
            "id": 10,
            "note": "comment",
            "position": {"new_path": "foo.py", "new_line": 5, "old_line": None},
        }
        mock_mr = MagicMock()
        mock_mr.diff_refs = {"base_sha": "aaa", "head_sha": "bbb", "start_sha": "ccc"}
        mock_mr.draft_notes.create = MagicMock(return_value=mock_draft)

        async def mock_to_thread(fn, *args, **kwargs):
            return fn(*args, **kwargs)

        service._project.mergerequests.get = MagicMock(return_value=mock_mr)
        with patch("asyncio.to_thread", side_effect=mock_to_thread):
            await service.add_inline_comment(1, "foo.py", 5, "comment", "new")

        call_args = mock_mr.draft_notes.create.call_args[0][0]
        position = call_args["position"]
        assert position["new_line"] == 5
        assert "old_line" not in position
        assert "line_code" not in position

    async def test_position_old_line_only_for_remove_line(self, service: CommentService) -> None:
        """削除行(old)のとき、position に old_line のみ含まれ new_line・line_code は含まれないこと。

        GitLab API 仕様:
        - 削除行: position[old_line] のみ送る。new_line は送らない
        - line_code はクライアントから送らない（GitLab がサーバー側で生成する）
        ref: https://docs.gitlab.com/api/discussions/
        """
        mock_draft = MagicMock()
        mock_draft.attributes = {
            "id": 11,
            "note": "comment",
            "position": {"new_path": "bar.py", "new_line": None, "old_line": 3},
        }
        mock_mr = MagicMock()
        mock_mr.diff_refs = {"base_sha": "a", "head_sha": "b", "start_sha": "c"}
        mock_mr.draft_notes.create = MagicMock(return_value=mock_draft)

        async def mock_to_thread(fn, *args, **kwargs):
            return fn(*args, **kwargs)

        service._project.mergerequests.get = MagicMock(return_value=mock_mr)
        with patch("asyncio.to_thread", side_effect=mock_to_thread):
            await service.add_inline_comment(1, "bar.py", 3, "comment", "old")

        call_args = mock_mr.draft_notes.create.call_args[0][0]
        position = call_args["position"]
        assert position["old_line"] == 3
        assert "new_line" not in position
        assert "line_code" not in position

    async def test_position_both_lines_for_context_line(self, service: CommentService) -> None:
        """コンテキスト行(変更なし行)のとき、position に new_line と old_line が両方含まれること。

        GitLab API 仕様:
        - 変更なし行: position[new_line] と position[old_line] を両方送る
        - line_code はクライアントから送らない（GitLab がサーバー側で生成する）
        ref: https://docs.gitlab.com/api/discussions/
        """
        mock_draft = MagicMock()
        mock_draft.attributes = {
            "id": 12,
            "note": "comment",
            "position": {"new_path": "baz.py", "new_line": 10, "old_line": 8},
        }
        mock_mr = MagicMock()
        mock_mr.diff_refs = {"base_sha": "x", "head_sha": "y", "start_sha": "z"}
        mock_mr.draft_notes.create = MagicMock(return_value=mock_draft)

        async def mock_to_thread(fn, *args, **kwargs):
            return fn(*args, **kwargs)

        service._project.mergerequests.get = MagicMock(return_value=mock_mr)
        with patch("asyncio.to_thread", side_effect=mock_to_thread):
            await service.add_inline_comment(1, "baz.py", 10, "comment", "new", old_line=8)

        call_args = mock_mr.draft_notes.create.call_args[0][0]
        position = call_args["position"]
        assert position["new_line"] == 10
        assert position["old_line"] == 8
        assert "line_code" not in position


class TestGetDiscussionsErrors:
    async def test_404_raises_mr_not_found(self, service: CommentService) -> None:
        exc = gitlab.exceptions.GitlabGetError(response_code=404, error_message="Not Found")

        async def mock_to_thread(fn, *args, **kwargs):
            raise exc

        with patch("asyncio.to_thread", side_effect=mock_to_thread):
            with pytest.raises(MRNotFoundError):
                await service.get_discussions(999)

    async def test_500_raises_connection_error(self, service: CommentService) -> None:
        exc = gitlab.exceptions.GitlabGetError(response_code=500, error_message="Server Error")

        async def mock_to_thread(fn, *args, **kwargs):
            raise exc

        with patch("asyncio.to_thread", side_effect=mock_to_thread):
            with pytest.raises(GitLabConnectionError):
                await service.get_discussions(1)


class TestReplyToDiscussionErrors:
    async def test_404_raises_mr_not_found(self, service: CommentService) -> None:
        exc = gitlab.exceptions.GitlabGetError(response_code=404, error_message="Not Found")

        async def mock_to_thread(fn, *args, **kwargs):
            raise exc

        with patch("asyncio.to_thread", side_effect=mock_to_thread):
            with pytest.raises(MRNotFoundError):
                await service.reply_to_discussion(999, "disc-id", "body")


class TestInvalidateCache:
    async def test_invalidate_specific_mr(self, service: CommentService) -> None:
        service._discussions_cache.set(1, [])
        service._discussions_cache.set(2, [])
        service.invalidate_cache(1)
        assert service._discussions_cache.get(1) is None
        assert service._discussions_cache.get(2) is not None

    async def test_invalidate_all(self, service: CommentService) -> None:
        service._discussions_cache.set(1, [])
        service._discussions_cache.set(2, [])
        service.invalidate_cache()
        assert service._discussions_cache.get(1) is None
        assert service._discussions_cache.get(2) is None


class TestConvertDiscussion:
    def test_system_notes_filtered(self, service: CommentService) -> None:
        raw = MagicMock()
        raw.id = "disc1"
        raw.attributes = {
            "notes": [
                {
                    "id": 1,
                    "author": {"username": "gitlab"},
                    "body": "system message",
                    "created_at": "",
                    "system": True,
                    "position": None,
                }
            ]
        }
        result = service._convert_discussion(raw)
        assert result is None

    def test_mixed_notes_keeps_user_notes(self, service: CommentService) -> None:
        raw = MagicMock()
        raw.id = "disc2"
        raw.attributes = {
            "notes": [
                {
                    "id": 1,
                    "author": {"username": "system"},
                    "body": "auto",
                    "created_at": "",
                    "system": True,
                    "position": None,
                },
                {
                    "id": 2,
                    "author": {"username": "user"},
                    "body": "comment",
                    "created_at": "",
                    "system": False,
                    "position": None,
                },
            ]
        }
        result = service._convert_discussion(raw)
        assert result is not None
        assert len(result.notes) == 1
        assert result.notes[0].author == "user"


class TestConvertDraftNote:
    def test_converts_with_current_username(self, service: CommentService) -> None:
        note = service._convert_draft_note({"id": 42, "note": "todo", "position": None})
        assert note.id == 42
        assert note.author == "me"
        assert note.body == "todo"
        assert note.is_draft is True

    def test_converts_position(self, service: CommentService) -> None:
        note = service._convert_draft_note(
            {
                "id": 1,
                "note": "x",
                "position": {"new_path": "foo.py", "new_line": 5, "old_line": None},
            }
        )
        assert note.position is not None
        assert note.position.file_path == "foo.py"
        assert note.position.new_line == 5


class TestGetDraftNotes:
    async def test_returns_draft_notes(self, service: CommentService) -> None:
        raw = MagicMock()
        raw.attributes = {"id": 7, "note": "pending", "position": None}
        mock_mr = MagicMock()
        mock_mr.draft_notes.list = MagicMock(return_value=[raw])

        async def mock_to_thread(fn, *args, **kwargs):
            return fn(*args, **kwargs)

        service._project.mergerequests.get = MagicMock(return_value=mock_mr)
        with patch("asyncio.to_thread", side_effect=mock_to_thread):
            result = await service.get_draft_notes(1)
        assert len(result) == 1
        assert result[0].id == 7
        assert result[0].is_draft is True

    async def test_404_raises_mr_not_found(self, service: CommentService) -> None:
        exc = gitlab.exceptions.GitlabGetError(response_code=404, error_message="Not Found")

        async def mock_to_thread(fn, *args, **kwargs):
            raise exc

        with patch("asyncio.to_thread", side_effect=mock_to_thread):
            with pytest.raises(MRNotFoundError):
                await service.get_draft_notes(999)


class TestPublishReview:
    async def test_bulk_publishes_and_invalidates_cache(self, service: CommentService) -> None:
        service._discussions_cache.set(1, [])
        mock_mr = MagicMock()
        mock_mr.draft_notes.bulk_publish = MagicMock()

        async def mock_to_thread(fn, *args, **kwargs):
            return fn(*args, **kwargs)

        service._project.mergerequests.get = MagicMock(return_value=mock_mr)
        with patch("asyncio.to_thread", side_effect=mock_to_thread):
            await service.publish_review(1)

        mock_mr.draft_notes.bulk_publish.assert_called_once()
        assert service._discussions_cache.get(1) is None

    async def test_404_raises_mr_not_found(self, service: CommentService) -> None:
        exc = gitlab.exceptions.GitlabGetError(response_code=404, error_message="Not Found")

        async def mock_to_thread(fn, *args, **kwargs):
            raise exc

        with patch("asyncio.to_thread", side_effect=mock_to_thread):
            with pytest.raises(MRNotFoundError):
                await service.publish_review(999)
