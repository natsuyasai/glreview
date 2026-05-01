"""GitLab API クライアント。python-gitlabのラッパー。"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

import gitlab
import gitlab.exceptions

from glreview.infrastructure import get_logger
from glreview.models import AppConfig
from glreview.services.exceptions import (
    GitLabAccessDeniedError,
    GitLabAuthError,
    GitLabConnectionError,
    GitLabProjectNotFoundError,
    GLReviewAPIError,
)

_CONNECT_TIMEOUT = 10
_READ_TIMEOUT = 30


@dataclass
class CurrentUser:
    """現在の認証ユーザー情報。"""

    id: int
    username: str


class GitLabClient:
    """python-gitlabのラッパー。認証・接続管理を担う。

    使用前に必ず connect() を呼び出すこと。
    """

    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._logger = get_logger(__name__)
        self._gl = gitlab.Gitlab(
            url=config.gitlab_url,
            private_token=config.token,
            timeout=(_CONNECT_TIMEOUT, _READ_TIMEOUT),
            ssl_verify=config.ssl_verify,
        )
        self._current_user: CurrentUser | None = None

    async def connect(self) -> None:
        """GitLab APIに接続し、認証を検証する。

        Raises:
            GitLabAuthError: 認証に失敗した場合。
            GitLabConnectionError: 接続に失敗した場合。
        """
        self._logger.debug("Connecting to GitLab: %s", self._config.gitlab_url)
        try:
            await asyncio.to_thread(self._gl.auth)
            user = self._gl.user
            self._current_user = CurrentUser(id=user.id, username=user.username)
            self._logger.debug("Authenticated as: %s", self._current_user.username)
        except gitlab.exceptions.GitlabAuthenticationError as exc:
            self._logger.error("GitLab authentication failed: %s", type(exc).__name__)
            raise GitLabAuthError("認証に失敗しました。トークンを確認してください。") from exc
        except (gitlab.exceptions.GitlabHttpError, OSError, TimeoutError) as exc:
            self._logger.error("GitLab connection failed: %s", type(exc).__name__)
            raise GitLabConnectionError(
                "GitLabサーバーへの接続に失敗しました。URLとネットワークを確認してください。"
            ) from exc

    async def get_project(self, project_path: str) -> gitlab.v4.objects.Project:
        """プロジェクトを取得する。

        Args:
            project_path: "group/project" または "group/subgroup/project" 形式のパス。

        Raises:
            GitLabProjectNotFoundError: プロジェクトが見つからない場合。
            GitLabAccessDeniedError: アクセス権限がない場合。
            GitLabConnectionError: 接続に失敗した場合。
        """
        self._logger.debug("Fetching project: %s", project_path)
        try:
            return await asyncio.to_thread(self._gl.projects.get, project_path)
        except gitlab.exceptions.GitlabGetError as exc:
            if exc.response_code == 404:
                raise GitLabProjectNotFoundError(
                    f"プロジェクト '{project_path}' が見つかりません。"
                ) from exc
            if exc.response_code == 403:
                raise GitLabAccessDeniedError(
                    f"プロジェクト '{project_path}' へのアクセス権限がありません。"
                ) from exc
            self._logger.error("GitLab API error fetching project: status=%s", exc.response_code)
            raise GitLabConnectionError("GitLabサーバーとの通信中にエラーが発生しました。") from exc
        except (OSError, TimeoutError) as exc:
            self._logger.error("Connection error: %s", type(exc).__name__)
            raise GitLabConnectionError(
                "接続がタイムアウトしました。ネットワーク接続を確認してください。"
            ) from exc

    async def get_current_user(self) -> CurrentUser:
        """現在の認証ユーザー情報を返す。connect() 後に使用可能。

        Raises:
            GitLabAuthError: connect() が呼ばれていない場合。
        """
        if self._current_user is None:
            raise GitLabAuthError("接続が確立されていません。connect() を先に呼び出してください。")
        return self._current_user

    def _wrap_api_error(self, exc: Exception) -> GLReviewAPIError:
        """python-gitlab例外を内部エラーに変換する。"""
        if isinstance(exc, gitlab.exceptions.GitlabAuthenticationError):
            return GitLabAuthError("認証に失敗しました。トークンを確認してください。")
        if isinstance(exc, gitlab.exceptions.GitlabGetError):
            if exc.response_code == 404:
                return GitLabProjectNotFoundError("指定されたリソースが見つかりません。")
            if exc.response_code == 403:
                return GitLabAccessDeniedError("アクセス権限がありません。")
        if isinstance(exc, (OSError, TimeoutError)):
            return GitLabConnectionError(
                "接続がタイムアウトしました。ネットワーク接続を確認してください。"
            )
        self._logger.error("Unexpected API error: %s", type(exc).__name__)
        return GitLabConnectionError("GitLabサーバーとの通信中にエラーが発生しました。")
