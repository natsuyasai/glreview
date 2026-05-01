"""glreview.services.gitlab_client のユニットテスト。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import gitlab.exceptions
import pytest

from glreview.models import AppConfig
from glreview.services.exceptions import (
    GitLabAccessDeniedError,
    GitLabAuthError,
    GitLabConnectionError,
    GitLabProjectNotFoundError,
)
from glreview.services.gitlab_client import GitLabClient


@pytest.fixture
def config() -> AppConfig:
    return AppConfig(gitlab_url="https://gitlab.example.com", token="glpat-test")


@pytest.fixture
def mock_gl() -> MagicMock:
    mock = MagicMock()
    mock.user = MagicMock(id=42, username="testuser")
    return mock


class TestGitLabClientConnect:
    async def test_connect_success(self, config: AppConfig, mock_gl: MagicMock) -> None:
        with patch("glreview.services.gitlab_client.gitlab.Gitlab", return_value=mock_gl):
            client = GitLabClient(config)
            with patch("asyncio.to_thread", new=AsyncMock(return_value=None)):
                await client.connect()
        user = await client.get_current_user()
        assert user.id == 42
        assert user.username == "testuser"

    async def test_connect_auth_failure(self, config: AppConfig) -> None:
        mock_gl = MagicMock()
        with patch("glreview.services.gitlab_client.gitlab.Gitlab", return_value=mock_gl):
            client = GitLabClient(config)
            with patch(
                "asyncio.to_thread",
                new=AsyncMock(side_effect=gitlab.exceptions.GitlabAuthenticationError("401", 401)),
            ):
                with pytest.raises(GitLabAuthError):
                    await client.connect()

    async def test_connect_network_error(self, config: AppConfig) -> None:
        mock_gl = MagicMock()
        with patch("glreview.services.gitlab_client.gitlab.Gitlab", return_value=mock_gl):
            client = GitLabClient(config)
            with patch(
                "asyncio.to_thread",
                new=AsyncMock(side_effect=OSError("connection refused")),
            ):
                with pytest.raises(GitLabConnectionError):
                    await client.connect()


class TestGitLabClientGetProject:
    async def test_get_project_success(self, config: AppConfig, mock_gl: MagicMock) -> None:
        mock_project = MagicMock()
        mock_gl.projects.get = MagicMock(return_value=mock_project)
        with patch("glreview.services.gitlab_client.gitlab.Gitlab", return_value=mock_gl):
            client = GitLabClient(config)
            with patch("asyncio.to_thread", new=AsyncMock(return_value=mock_project)):
                project = await client.get_project("group/project")
        assert project is mock_project

    async def test_get_project_not_found(self, config: AppConfig, mock_gl: MagicMock) -> None:
        exc = gitlab.exceptions.GitlabGetError("404", 404)
        with patch("glreview.services.gitlab_client.gitlab.Gitlab", return_value=mock_gl):
            client = GitLabClient(config)
            with patch("asyncio.to_thread", new=AsyncMock(side_effect=exc)):
                with pytest.raises(GitLabProjectNotFoundError):
                    await client.get_project("group/missing")

    async def test_get_project_forbidden(self, config: AppConfig, mock_gl: MagicMock) -> None:
        exc = gitlab.exceptions.GitlabGetError("403", 403)
        with patch("glreview.services.gitlab_client.gitlab.Gitlab", return_value=mock_gl):
            client = GitLabClient(config)
            with patch("asyncio.to_thread", new=AsyncMock(side_effect=exc)):
                with pytest.raises(GitLabAccessDeniedError):
                    await client.get_project("group/secret")


class TestGitLabClientGetCurrentUser:
    async def test_not_connected_raises(self, config: AppConfig, mock_gl: MagicMock) -> None:
        with patch("glreview.services.gitlab_client.gitlab.Gitlab", return_value=mock_gl):
            client = GitLabClient(config)
            with pytest.raises(GitLabAuthError):
                await client.get_current_user()


class TestWrapApiError:
    def test_wraps_auth_error(self, config: AppConfig) -> None:
        with patch("glreview.services.gitlab_client.gitlab.Gitlab"):
            client = GitLabClient(config)
        exc = gitlab.exceptions.GitlabAuthenticationError("401", 401)
        result = client._wrap_api_error(exc)
        assert isinstance(result, GitLabAuthError)

    def test_wraps_404(self, config: AppConfig) -> None:
        with patch("glreview.services.gitlab_client.gitlab.Gitlab"):
            client = GitLabClient(config)
        exc = gitlab.exceptions.GitlabGetError("404", 404)
        result = client._wrap_api_error(exc)
        assert isinstance(result, GitLabProjectNotFoundError)

    def test_wraps_timeout(self, config: AppConfig) -> None:
        with patch("glreview.services.gitlab_client.gitlab.Gitlab"):
            client = GitLabClient(config)
        result = client._wrap_api_error(TimeoutError("timeout"))
        assert isinstance(result, GitLabConnectionError)
