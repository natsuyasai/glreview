"""glreview.services.mr_service のユニットテスト。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import gitlab.exceptions
import pytest

from glreview.models import AppConfig
from glreview.services.exceptions import (
    FileNotFoundInMRError,
    GitLabConnectionError,
    MRNotFoundError,
)
from glreview.services.gitlab_client import CurrentUser, GitLabClient
from glreview.services.mr_service import MRService
from glreview.services.types import PaginatedResult


def _make_mr(
    iid: int = 1,
    title: str = "Test MR",
    author_username: str = "alice",
    assignee_username: str | None = None,
    assignee_id: int | None = None,
    state: str = "opened",
    labels: list[str] | None = None,
    updated_at: str = "2026-01-01T00:00:00Z",
) -> MagicMock:
    mr = MagicMock()
    mr.iid = iid
    mr.title = title
    mr.author = {"username": author_username}
    mr.assignee = {"username": assignee_username, "id": assignee_id} if assignee_username else None
    mr.state = state
    mr.labels = labels or []
    mr.updated_at = updated_at
    mr.description = "desc"
    mr.milestone = None
    mr.head_pipeline = None
    mr.web_url = f"https://gitlab.example.com/mr/{iid}"
    mr.created_at = "2026-01-01T00:00:00Z"
    mr.diff_refs = {"base_sha": "aaa", "head_sha": "bbb", "start_sha": "ccc"}
    return mr


@pytest.fixture
def config() -> AppConfig:
    return AppConfig(gitlab_url="https://gitlab.example.com", token="glpat-test")


@pytest.fixture
def mock_client(config: AppConfig) -> MagicMock:
    client = MagicMock(spec=GitLabClient)
    client._config = config
    client.get_project = AsyncMock(return_value=MagicMock())
    client.get_current_user = AsyncMock(return_value=CurrentUser(id=10, username="me"))
    client._wrap_api_error = MagicMock(side_effect=lambda e: e)
    return client


@pytest.fixture
async def service(mock_client: MagicMock) -> MRService:
    svc = MRService(mock_client, "group/project")
    await svc.load()
    return svc


class TestMRServiceLoad:
    async def test_load_sets_project_and_user(self, mock_client: MagicMock) -> None:
        svc = MRService(mock_client, "group/project")
        await svc.load()
        assert svc._project is not None
        assert svc._current_user_id == 10


def _make_mr_list(*mrs) -> MagicMock:
    """python-gitlabのRESTリストオブジェクトをモックする。_next_url属性を持つ。"""
    mock_list = MagicMock()
    mock_list.__iter__ = MagicMock(return_value=iter(list(mrs)))
    mock_list._next_url = None
    return mock_list


class TestGetAssignedToMe:
    async def test_returns_paginated_result(self, service: MRService) -> None:
        mr = _make_mr(iid=1, assignee_username="me", assignee_id=10)
        mock_list = _make_mr_list(mr)
        with patch("asyncio.to_thread", new=AsyncMock(return_value=mock_list)):
            result = await service.get_assigned_to_me()
        assert isinstance(result, PaginatedResult)
        assert len(result.items) == 1
        assert result.items[0].iid == 1
        assert result.has_next_page is False


class TestGetAssignedToOthers:
    async def test_excludes_current_user(self, service: MRService) -> None:
        mr_me = _make_mr(iid=1, assignee_username="me", assignee_id=10)
        mr_other = _make_mr(iid=2, assignee_username="bob", assignee_id=20)
        mock_list = _make_mr_list(mr_me, mr_other)
        with patch("asyncio.to_thread", new=AsyncMock(return_value=mock_list)):
            result = await service.get_assigned_to_others()
        assert len(result.items) == 1
        assert result.items[0].iid == 2


class TestConvertToSummary:
    def test_basic_conversion(self, service: MRService) -> None:
        mr = _make_mr(iid=5, title="My MR", author_username="alice")
        summary = service._convert_to_summary(mr)
        assert summary.iid == 5
        assert summary.title == "My MR"
        assert summary.author == "alice"
        assert summary.assignee is None

    def test_with_assignee(self, service: MRService) -> None:
        mr = _make_mr(assignee_username="bob", assignee_id=20)
        summary = service._convert_to_summary(mr)
        assert summary.assignee == "bob"


class TestConvertToDetail:
    def test_basic_conversion(self, service: MRService) -> None:
        mr = _make_mr(iid=3)
        detail = service._convert_to_detail(mr)
        assert detail.iid == 3
        assert detail.description == "desc"
        assert detail.milestone is None
        assert detail.pipeline_status is None

    def test_with_milestone(self, service: MRService) -> None:
        mr = _make_mr()
        mr.milestone = {"title": "v1.0"}
        detail = service._convert_to_detail(mr)
        assert detail.milestone == "v1.0"

    def test_with_pipeline(self, service: MRService) -> None:
        mr = _make_mr()
        mr.head_pipeline = {"status": "passed"}
        detail = service._convert_to_detail(mr)
        assert detail.pipeline_status == "passed"


class TestGetMrDetail:
    async def test_cache_miss_then_hit(self, service: MRService) -> None:
        mr = _make_mr(iid=7)
        with patch("asyncio.to_thread", new=AsyncMock(return_value=mr)):
            detail1 = await service.get_mr_detail(7)
        # 2回目はキャッシュから(to_thread呼ばれない)
        detail2 = service._detail_cache.get(7)
        assert detail1.iid == 7
        assert detail2 is not None
        assert detail2.iid == 7

    async def test_invalidate_cache(self, service: MRService) -> None:
        mr = _make_mr(iid=7)
        with patch("asyncio.to_thread", new=AsyncMock(return_value=mr)):
            await service.get_mr_detail(7)
        service.invalidate_cache(7)
        assert service._detail_cache.get(7) is None

    async def test_invalidate_all_cache(self, service: MRService) -> None:
        mr = _make_mr(iid=7)
        with patch("asyncio.to_thread", new=AsyncMock(return_value=mr)):
            await service.get_mr_detail(7)
        service.invalidate_cache()
        assert service._detail_cache.get(7) is None


class TestGetMrDiff:
    async def test_file_found(self, service: MRService) -> None:
        mr = MagicMock()
        mr.changes = MagicMock(
            return_value={
                "changes": [
                    {
                        "old_path": "foo.py",
                        "new_path": "foo.py",
                        "diff": "@@ -1 +1 @@ foo",
                        "new_file": False,
                        "deleted_file": False,
                        "renamed_file": False,
                    }
                ]
            }
        )

        async def mock_to_thread(fn, *args, **kwargs):
            return fn(*args, **kwargs)

        with patch("asyncio.to_thread", side_effect=mock_to_thread):
            service._project.mergerequests.get = MagicMock(return_value=mr)
            diff = await service.get_mr_diff(1, "foo.py")
        assert diff.file_path == "foo.py"
        assert "@@ -1 +1 @@" in diff.diff

    async def test_file_not_found_raises(self, service: MRService) -> None:
        mr = MagicMock()
        mr.changes = MagicMock(return_value={"changes": []})

        async def mock_to_thread(fn, *args, **kwargs):
            return fn(*args, **kwargs)

        with patch("asyncio.to_thread", side_effect=mock_to_thread):
            service._project.mergerequests.get = MagicMock(return_value=mr)
            with pytest.raises(FileNotFoundInMRError):
                await service.get_mr_diff(1, "missing.py")

    async def test_404_raises_mr_not_found(self, service: MRService) -> None:
        exc = gitlab.exceptions.GitlabGetError(response_code=404, error_message="Not Found")

        async def mock_to_thread(fn, *args, **kwargs):
            raise exc

        with patch("asyncio.to_thread", side_effect=mock_to_thread):
            with pytest.raises(MRNotFoundError):
                await service.get_mr_diff(1, "foo.py")

    async def test_cache_hit_returns_cached(self, service: MRService) -> None:
        mr = MagicMock()
        mr.changes = MagicMock(
            return_value={
                "changes": [
                    {
                        "old_path": "bar.py",
                        "new_path": "bar.py",
                        "diff": "@@ -1 +1 @@",
                        "new_file": False,
                        "deleted_file": False,
                        "renamed_file": False,
                    }
                ]
            }
        )

        async def mock_to_thread(fn, *args, **kwargs):
            return fn(*args, **kwargs)

        with patch("asyncio.to_thread", side_effect=mock_to_thread):
            service._project.mergerequests.get = MagicMock(return_value=mr)
            diff1 = await service.get_mr_diff(1, "bar.py")
        diff2 = service._diff_cache.get((1, "bar.py"))
        assert diff1.file_path == diff2.file_path


class TestGetMrChanges:
    async def test_returns_file_changes(self, service: MRService) -> None:
        mr = MagicMock()
        mr.changes = MagicMock(
            return_value={
                "changes": [
                    {
                        "old_path": "a.py",
                        "new_path": "a.py",
                        "new_file": False,
                        "deleted_file": False,
                        "renamed_file": False,
                    }
                ]
            }
        )

        async def mock_to_thread(fn, *args, **kwargs):
            return fn(*args, **kwargs)

        with patch("asyncio.to_thread", side_effect=mock_to_thread):
            service._project.mergerequests.get = MagicMock(return_value=mr)
            changes = await service.get_mr_changes(1)
        assert len(changes) == 1
        assert changes[0].new_path == "a.py"

    async def test_cache_hit(self, service: MRService) -> None:
        mr = MagicMock()
        mr.changes = MagicMock(return_value={"changes": []})

        async def mock_to_thread(fn, *args, **kwargs):
            return fn(*args, **kwargs)

        with patch("asyncio.to_thread", side_effect=mock_to_thread):
            service._project.mergerequests.get = MagicMock(return_value=mr)
            r1 = await service.get_mr_changes(1)
        r2 = service._changes_cache.get(1)
        assert r1 is r2

    async def test_404_raises_mr_not_found(self, service: MRService) -> None:
        exc = gitlab.exceptions.GitlabGetError(response_code=404, error_message="Not Found")

        async def mock_to_thread(fn, *args, **kwargs):
            raise exc

        with patch("asyncio.to_thread", side_effect=mock_to_thread):
            with pytest.raises(MRNotFoundError):
                await service.get_mr_changes(1)


class TestGetReviewerIsMe:
    async def test_returns_paginated_result(self, service: MRService) -> None:
        mr = _make_mr(iid=5)
        mock_list = _make_mr_list(mr)
        with patch("asyncio.to_thread", new=AsyncMock(return_value=mock_list)):
            result = await service.get_reviewer_is_me()
        assert isinstance(result, PaginatedResult)
        assert len(result.items) == 1


class TestGetCreatedByMe:
    async def test_returns_paginated_result(self, service: MRService) -> None:
        mr = _make_mr(iid=3, author_username="me")
        mock_list = _make_mr_list(mr)
        with patch("asyncio.to_thread", new=AsyncMock(return_value=mock_list)):
            result = await service.get_created_by_me()
        assert isinstance(result, PaginatedResult)
        assert len(result.items) == 1


class TestGetUnassigned:
    async def test_returns_paginated_result(self, service: MRService) -> None:
        mr = _make_mr(iid=4)
        mock_list = _make_mr_list(mr)
        with patch("asyncio.to_thread", new=AsyncMock(return_value=mock_list)):
            result = await service.get_unassigned()
        assert isinstance(result, PaginatedResult)


class TestGetMrDetailErrors:
    async def test_404_raises_mr_not_found(self, service: MRService) -> None:
        exc = gitlab.exceptions.GitlabGetError(response_code=404, error_message="Not Found")

        async def mock_to_thread(fn, *args, **kwargs):
            raise exc

        with patch("asyncio.to_thread", side_effect=mock_to_thread):
            with pytest.raises(MRNotFoundError):
                await service.get_mr_detail(999)

    async def test_non_404_raises_connection_error(self, service: MRService) -> None:
        exc = gitlab.exceptions.GitlabGetError(response_code=500, error_message="Server Error")

        async def mock_to_thread(fn, *args, **kwargs):
            raise exc

        with patch("asyncio.to_thread", side_effect=mock_to_thread):
            with pytest.raises(GitLabConnectionError):
                await service.get_mr_detail(1)


class TestGetFileLinesMethod:
    async def test_returns_lines(self, service: MRService) -> None:
        from glreview.models import MergeRequestDetail

        detail = MergeRequestDetail(
            iid=1,
            title="T",
            description="",
            author="alice",
            status="opened",
            labels=[],
            web_url="",
            created_at="",
            updated_at="",
            source_branch="feature",
        )
        service._detail_cache.set(1, detail)

        mock_file = MagicMock()
        mock_file.decode.return_value.decode.return_value.splitlines.return_value = [
            "line1",
            "line2",
        ]

        async def mock_to_thread(fn, *args, **kwargs):
            return mock_file

        with patch("asyncio.to_thread", side_effect=mock_to_thread):
            lines = await service.get_file_lines(1, "foo.py")
        assert "line1" in lines
        assert "line2" in lines

    async def test_file_not_found_raises(self, service: MRService) -> None:
        mr = _make_mr(iid=2)
        mr.source_branch = "feature"
        service._detail_cache.set(2, service._convert_to_detail(mr))

        exc = gitlab.exceptions.GitlabGetError(response_code=404, error_message="Not Found")

        async def mock_to_thread(fn, *args, **kwargs):
            raise exc

        with patch("asyncio.to_thread", side_effect=mock_to_thread):
            with pytest.raises(FileNotFoundInMRError):
                await service.get_file_lines(2, "nonexistent.py")


class TestGetOrderBy:
    def test_default_order_by(self, service: MRService) -> None:
        service._client._config.sort_order = "updated_at"
        assert service._get_order_by() == "updated_at"

    def test_invalid_order_by_falls_back_to_default(self, service: MRService) -> None:
        service._client._config.sort_order = "invalid_field"
        assert service._get_order_by() == "updated_at"

    def test_created_at_order_by(self, service: MRService) -> None:
        service._client._config.sort_order = "created_at"
        assert service._get_order_by() == "created_at"


class TestGetMrListByCategory:
    async def test_dispatches_to_correct_method(self, service: MRService) -> None:
        from glreview.services.types import MRCategory

        empty = PaginatedResult(items=[], has_next_page=False, next_page=None)
        with patch.object(service, "get_assigned_to_me", new=AsyncMock(return_value=empty)) as m:
            result = await service._get_mr_list_by_category(MRCategory.ASSIGNED_TO_ME)
        m.assert_called_once_with(page=1)
        assert result is empty


class TestConvertToFileChange:
    def test_new_file(self, service: MRService) -> None:
        change = {
            "old_path": "",
            "new_path": "new_file.py",
            "new_file": True,
            "deleted_file": False,
            "renamed_file": False,
        }
        fc = service._convert_to_file_change(change)
        assert fc.new_file is True
        assert fc.new_path == "new_file.py"

    def test_deleted_file(self, service: MRService) -> None:
        change = {
            "old_path": "old.py",
            "new_path": "old.py",
            "new_file": False,
            "deleted_file": True,
            "renamed_file": False,
        }
        fc = service._convert_to_file_change(change)
        assert fc.deleted_file is True

    def test_missing_keys_use_defaults(self, service: MRService) -> None:
        fc = service._convert_to_file_change({})
        assert fc.old_path == ""
        assert fc.new_path == ""
        assert fc.new_file is False


class TestPaginatedResult:
    async def test_has_next_page_when_next_url_present(self, service: MRService) -> None:
        mr = _make_mr(iid=1)
        mock_list = _make_mr_list(mr)
        mock_list._next_url = "https://gitlab.example.com/api/v4/projects/1/mrs?page=2"
        with patch("asyncio.to_thread", new=AsyncMock(return_value=mock_list)):
            result = await service.get_assigned_to_me(page=1)
        assert result.has_next_page is True
        assert result.next_page == 2
