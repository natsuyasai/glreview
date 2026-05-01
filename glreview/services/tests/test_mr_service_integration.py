"""glreview.services の統合テスト。実際のGitLabインスタンスへの接続が必要。

環境変数:
  LAZYGITLAB_TEST_TOKEN   : GitLab Personal Access Token
  LAZYGITLAB_TEST_URL     : GitLabのURL(例: https://gitlab.com)
  LAZYGITLAB_TEST_PROJECT : テスト対象プロジェクトパス(例: group/project)

環境変数が未設定の場合はすべてのテストをスキップする。
"""

from __future__ import annotations

import os

import pytest

from glreview.models import AppConfig
from glreview.services.gitlab_client import GitLabClient
from glreview.services.mr_service import MRService

pytestmark = pytest.mark.integration

_TOKEN = os.environ.get("LAZYGITLAB_TEST_TOKEN")
_URL = os.environ.get("LAZYGITLAB_TEST_URL")
_PROJECT = os.environ.get("LAZYGITLAB_TEST_PROJECT")

_SKIP = not (_TOKEN and _URL and _PROJECT)
_SKIP_REASON = (
    "統合テストには LAZYGITLAB_TEST_TOKEN, LAZYGITLAB_TEST_URL, "
    "LAZYGITLAB_TEST_PROJECT 環境変数が必要です。"
)


@pytest.fixture
async def client() -> GitLabClient:
    config = AppConfig(gitlab_url=_URL or "", token=_TOKEN or "")
    c = GitLabClient(config)
    await c.connect()
    return c


@pytest.fixture
async def mr_service(client: GitLabClient) -> MRService:
    svc = MRService(client, _PROJECT or "")
    await svc.load()
    return svc


@pytest.mark.skipif(_SKIP, reason=_SKIP_REASON)
class TestMRServiceIntegration:
    async def test_get_assigned_to_me(self, mr_service: MRService) -> None:
        result = await mr_service.get_assigned_to_me()
        assert result is not None
        assert isinstance(result.items, list)

    async def test_get_created_by_me(self, mr_service: MRService) -> None:
        result = await mr_service.get_created_by_me()
        assert result is not None

    async def test_get_unassigned(self, mr_service: MRService) -> None:
        result = await mr_service.get_unassigned()
        assert result is not None

    async def test_get_assigned_to_others(self, mr_service: MRService) -> None:
        result = await mr_service.get_assigned_to_others()
        assert result is not None
