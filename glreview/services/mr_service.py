"""MR関連のAPIサービス。MR一覧・詳細・差分の取得を担う。"""

from __future__ import annotations

import asyncio
from typing import Any

import gitlab.exceptions

from glreview.infrastructure import get_logger
from glreview.models import (
    FileChange,
    FileDiff,
    MergeRequestDetail,
    MergeRequestSummary,
)
from glreview.services.cache import LRUCache
from glreview.services.exceptions import (
    FileNotFoundInMRError,
    GitLabConnectionError,
    MRNotFoundError,
)
from glreview.services.gitlab_client import GitLabClient
from glreview.services.types import MRCategory, PaginatedResult

_CACHE_DETAIL_MAX = 100
_CACHE_CHANGES_MAX = 100
_CACHE_DIFF_MAX = 50

_VALID_ORDER_BY = {"updated_at", "created_at"}
_DEFAULT_ORDER_BY = "updated_at"


class MRService:
    """MR一覧・詳細・差分の取得サービス。

    使用前に必ず load() を呼び出すこと。
    """

    def __init__(self, client: GitLabClient, project_path: str) -> None:
        self._client = client
        self._project_path = project_path
        self._project: Any = None
        self._current_user_id: int | None = None
        self._logger = get_logger(__name__)
        self._detail_cache: LRUCache[int, MergeRequestDetail] = LRUCache(_CACHE_DETAIL_MAX)
        self._changes_cache: LRUCache[int, list[FileChange]] = LRUCache(_CACHE_CHANGES_MAX)
        self._diff_cache: LRUCache[tuple[int, str], FileDiff] = LRUCache(_CACHE_DIFF_MAX)

    async def load(self) -> None:
        """プロジェクトと現在ユーザー情報を非同期で初期化する。"""
        self._project = await self._client.get_project(self._project_path)
        user = await self._client.get_current_user()
        self._current_user_id = user.id
        self._logger.debug(
            "MRService loaded: project=%s, user_id=%s",
            self._project_path,
            self._current_user_id,
        )

    def _get_order_by(self) -> str:
        order_by = getattr(self._client._config, "sort_order", _DEFAULT_ORDER_BY)
        if order_by not in _VALID_ORDER_BY:
            self._logger.warning(
                "Invalid sort_order '%s', falling back to '%s'",
                order_by,
                _DEFAULT_ORDER_BY,
            )
            return _DEFAULT_ORDER_BY
        return order_by

    def _build_list_kwargs(self, **extra: Any) -> dict[str, Any]:
        return {
            "state": "opened",
            "order_by": self._get_order_by(),
            "sort": "desc",
            "per_page": 20,
            **extra,
        }

    def _parse_paginated(self, mr_list: Any, page: int) -> PaginatedResult:
        items = [self._convert_to_summary(mr) for mr in mr_list]
        # python-gitlabのRESTオブジェクトは _next_url 属性でページ情報を保持する
        has_next = getattr(mr_list, "_next_url", None) is not None
        next_page = page + 1 if has_next else None
        return PaginatedResult(items=items, has_next_page=has_next, next_page=next_page)

    async def get_assigned_to_me(self, page: int = 1) -> PaginatedResult:
        """自身に割り当てられているMR一覧を取得する。"""
        kwargs = self._build_list_kwargs(assignee_id=self._current_user_id, page=page)
        self._logger.debug("Fetching MRs assigned to me (page=%s)", page)
        try:
            mr_list = await asyncio.to_thread(self._project.mergerequests.list, **kwargs)
        except Exception as exc:
            raise self._client._wrap_api_error(exc) from exc
        return self._parse_paginated(mr_list, page)

    async def get_created_by_me(self, page: int = 1) -> PaginatedResult:
        """自身が作成したMR一覧を取得する。"""
        kwargs = self._build_list_kwargs(author_id=self._current_user_id, page=page)
        self._logger.debug("Fetching MRs created by me (page=%s)", page)
        try:
            mr_list = await asyncio.to_thread(self._project.mergerequests.list, **kwargs)
        except Exception as exc:
            raise self._client._wrap_api_error(exc) from exc
        return self._parse_paginated(mr_list, page)

    async def get_unassigned(self, page: int = 1) -> PaginatedResult:
        """未割当のMR一覧を取得する。"""
        kwargs = self._build_list_kwargs(assignee_id="None", page=page)
        self._logger.debug("Fetching unassigned MRs (page=%s)", page)
        try:
            mr_list = await asyncio.to_thread(self._project.mergerequests.list, **kwargs)
        except Exception as exc:
            raise self._client._wrap_api_error(exc) from exc
        return self._parse_paginated(mr_list, page)

    async def get_reviewer_is_me(self, page: int = 1) -> PaginatedResult:
        """自身がレビュアーに設定されているMR一覧を取得する。"""
        kwargs = self._build_list_kwargs(reviewer_id=self._current_user_id, page=page)
        self._logger.debug("Fetching MRs where I am reviewer (page=%s)", page)
        try:
            mr_list = await asyncio.to_thread(self._project.mergerequests.list, **kwargs)
        except Exception as exc:
            raise self._client._wrap_api_error(exc) from exc
        return self._parse_paginated(mr_list, page)

    async def get_assigned_to_others(self, page: int = 1) -> PaginatedResult:
        """自身以外に割り当てられているMR一覧を取得する。"""
        kwargs = self._build_list_kwargs(assignee_id="Any", page=page)
        self._logger.debug("Fetching MRs assigned to others (page=%s)", page)
        try:
            mr_list = await asyncio.to_thread(self._project.mergerequests.list, **kwargs)
        except Exception as exc:
            raise self._client._wrap_api_error(exc) from exc
        # 自ユーザーのMRをクライアント側で除外する
        filtered = [
            mr
            for mr in mr_list
            if not (mr.assignee and mr.assignee.get("id") == self._current_user_id)
        ]
        items = [self._convert_to_summary(mr) for mr in filtered]
        has_next = getattr(mr_list, "_next_url", None) is not None
        next_page = page + 1 if has_next else None
        return PaginatedResult(items=items, has_next_page=has_next, next_page=next_page)

    async def _get_mr_list_by_category(
        self, category: MRCategory, page: int = 1
    ) -> PaginatedResult:
        """カテゴリに応じたMR一覧取得メソッドにディスパッチする。"""
        dispatch = {
            MRCategory.ASSIGNED_TO_ME: self.get_assigned_to_me,
            MRCategory.REVIEWER_IS_ME: self.get_reviewer_is_me,
            MRCategory.CREATED_BY_ME: self.get_created_by_me,
            MRCategory.UNASSIGNED: self.get_unassigned,
            MRCategory.ASSIGNED_TO_OTHERS: self.get_assigned_to_others,
        }
        return await dispatch[category](page=page)

    async def get_mr_detail(self, mr_iid: int) -> MergeRequestDetail:
        """MR詳細を取得する(キャッシュ対象)。

        Raises:
            MRNotFoundError: 指定IIDのMRが存在しない場合。
            GitLabConnectionError: API通信エラー。
        """
        cached = self._detail_cache.get(mr_iid)
        if cached is not None:
            self._logger.debug("Cache hit: MR detail iid=%s", mr_iid)
            return cached

        self._logger.debug("Fetching MR detail: iid=%s", mr_iid)
        try:
            mr = await asyncio.to_thread(self._project.mergerequests.get, mr_iid)
        except gitlab.exceptions.GitlabGetError as exc:
            if exc.response_code == 404:
                raise MRNotFoundError(f"MR !{mr_iid} が見つかりません。") from exc
            raise GitLabConnectionError("GitLabサーバーとの通信中にエラーが発生しました。") from exc
        except Exception as exc:
            raise self._client._wrap_api_error(exc) from exc

        detail = self._convert_to_detail(mr)
        self._detail_cache.set(mr_iid, detail)
        return detail

    async def get_mr_changes(self, mr_iid: int) -> list[FileChange]:
        """MRの変更ファイル一覧を取得する(キャッシュ対象)。

        Raises:
            MRNotFoundError: 指定IIDのMRが存在しない場合。
            GitLabConnectionError: API通信エラー。
        """
        cached = self._changes_cache.get(mr_iid)
        if cached is not None:
            self._logger.debug("Cache hit: MR changes iid=%s", mr_iid)
            return cached

        self._logger.debug("Fetching MR changes: iid=%s", mr_iid)
        try:
            mr = await asyncio.to_thread(self._project.mergerequests.get, mr_iid, lazy=True)
            changes_data = await asyncio.to_thread(mr.changes)
        except gitlab.exceptions.GitlabGetError as exc:
            if exc.response_code == 404:
                raise MRNotFoundError(f"MR !{mr_iid} が見つかりません。") from exc
            raise GitLabConnectionError("GitLabサーバーとの通信中にエラーが発生しました。") from exc
        except Exception as exc:
            raise self._client._wrap_api_error(exc) from exc

        changes = [self._convert_to_file_change(c) for c in changes_data.get("changes", [])]
        self._changes_cache.set(mr_iid, changes)
        return changes

    async def get_mr_diff(self, mr_iid: int, file_path: str) -> FileDiff:
        """指定ファイルの差分を取得する(キャッシュ対象、遅延取得)。

        Raises:
            MRNotFoundError: 指定IIDのMRが存在しない場合。
            FileNotFoundInMRError: MR内に指定ファイルが存在しない場合。
            GitLabConnectionError: API通信エラー。
        """
        cache_key = (mr_iid, file_path)
        cached = self._diff_cache.get(cache_key)
        if cached is not None:
            self._logger.debug("Cache hit: diff iid=%s file=%s", mr_iid, file_path)
            return cached

        self._logger.debug("Fetching MR diff: iid=%s file=%s", mr_iid, file_path)
        try:
            mr = await asyncio.to_thread(self._project.mergerequests.get, mr_iid, lazy=True)
            changes_data = await asyncio.to_thread(mr.changes)
        except gitlab.exceptions.GitlabGetError as exc:
            if exc.response_code == 404:
                raise MRNotFoundError(f"MR !{mr_iid} が見つかりません。") from exc
            raise GitLabConnectionError("GitLabサーバーとの通信中にエラーが発生しました。") from exc
        except Exception as exc:
            raise self._client._wrap_api_error(exc) from exc

        for change in changes_data.get("changes", []):
            if change.get("new_path") == file_path or change.get("old_path") == file_path:
                file_diff = FileDiff(
                    file_path=change.get("new_path", file_path),
                    diff=change.get("diff", ""),
                    old_path=change.get("old_path", file_path),
                    new_path=change.get("new_path", file_path),
                )
                self._diff_cache.set(cache_key, file_diff)
                return file_diff

        raise FileNotFoundInMRError(f"MR !{mr_iid} にファイル '{file_path}' が見つかりません。")

    async def get_file_lines(self, mr_iid: int, file_path: str) -> list[str]:
        """MR の source_branch でのファイル内容を行リストで返す。

        Raises:
            FileNotFoundInMRError: ファイルが存在しない場合。
            GitLabConnectionError: API通信エラー。
        """
        detail = await self.get_mr_detail(mr_iid)
        ref = detail.source_branch or "HEAD"
        self._logger.debug("Fetching file content: iid=%s file=%s ref=%s", mr_iid, file_path, ref)
        try:
            f = await asyncio.to_thread(self._project.files.get, file_path, ref=ref)
            content = f.decode().decode("utf-8", errors="replace")
            return content.splitlines()
        except gitlab.exceptions.GitlabGetError as exc:
            if exc.response_code == 404:
                raise FileNotFoundInMRError(
                    f"File '{file_path}' not found in MR !{mr_iid}"
                ) from exc
            raise GitLabConnectionError("GitLabサーバーとの通信中にエラーが発生しました。") from exc
        except Exception as exc:
            raise self._client._wrap_api_error(exc) from exc

    def invalidate_cache(self, mr_iid: int | None = None) -> None:
        """キャッシュを無効化する。mr_iid=Noneで全クリア。"""
        if mr_iid is None:
            self._detail_cache.clear()
            self._changes_cache.clear()
            self._diff_cache.clear()
            self._logger.debug("All MR caches cleared")
        else:
            self._detail_cache.delete(mr_iid)
            self._changes_cache.delete(mr_iid)
            # 差分キャッシュはファイルパスを含むため前方一致で削除
            keys_to_delete = [k for k in self._diff_cache._cache if k[0] == mr_iid]
            for key in keys_to_delete:
                self._diff_cache.delete(key)
            self._logger.debug("MR cache cleared for iid=%s", mr_iid)

    def _convert_to_summary(self, mr: Any) -> MergeRequestSummary:
        """python-gitlab MergeRequest オブジェクトを MergeRequestSummary に変換する。"""
        assignee = None
        if mr.assignee:
            assignee = mr.assignee.get("username")
        return MergeRequestSummary(
            iid=mr.iid,
            title=mr.title,
            author=mr.author.get("username", "") if mr.author else "",
            assignee=assignee,
            status=mr.state,
            labels=list(mr.labels) if mr.labels else [],
            updated_at=mr.updated_at or "",
        )

    def _convert_to_detail(self, mr: Any) -> MergeRequestDetail:
        """python-gitlab MergeRequest オブジェクトを MergeRequestDetail に変換する。"""
        assignee = None
        if mr.assignee:
            assignee = mr.assignee.get("username")

        milestone = None
        if mr.milestone:
            milestone = mr.milestone.get("title")

        pipeline_status = None
        if mr.head_pipeline:
            pipeline_status = mr.head_pipeline.get("status")

        return MergeRequestDetail(
            iid=mr.iid,
            title=mr.title,
            description=mr.description or "",
            author=mr.author.get("username", "") if mr.author else "",
            assignee=assignee,
            status=mr.state,
            labels=list(mr.labels) if mr.labels else [],
            milestone=milestone,
            pipeline_status=pipeline_status,
            web_url=mr.web_url or "",
            created_at=mr.created_at or "",
            updated_at=mr.updated_at or "",
            source_branch=mr.source_branch or "",
        )

    def _convert_to_file_change(self, change: dict[str, Any]) -> FileChange:
        """変更情報辞書を FileChange に変換する。"""
        return FileChange(
            old_path=change.get("old_path", ""),
            new_path=change.get("new_path", ""),
            new_file=bool(change.get("new_file", False)),
            deleted_file=bool(change.get("deleted_file", False)),
            renamed_file=bool(change.get("renamed_file", False)),
        )
