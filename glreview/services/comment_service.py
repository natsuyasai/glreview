"""コメント関連のAPIサービス。ディスカッション取得・コメント投稿を担う。"""

from __future__ import annotations

import asyncio
import hashlib
from typing import Any

import gitlab.exceptions

from glreview.infrastructure import get_logger
from glreview.models import Discussion, Note, NotePosition
from glreview.services.cache import LRUCache
from glreview.services.exceptions import (
    DiscussionNotFoundError,
    EmptyCommentError,
    GitLabConnectionError,
    MRNotFoundError,
)
from glreview.services.gitlab_client import GitLabClient

_CACHE_DISCUSSIONS_MAX = 100


def _generate_line_code(file_path: str, old_line: int | None, new_line: int | None) -> str:
    """GitLab diff コメント用の line_code を生成する。

    形式: sha1(file_path)_{old_line}_{new_line}
    行が存在しない側は 0 を使う。
    """
    sha = hashlib.sha1(file_path.encode()).hexdigest()  # noqa: S324
    return f"{sha}_{old_line or 0}_{new_line or 0}"


class CommentService:
    """MRのディスカッション取得・コメント投稿サービス。

    使用前に必ず load() を呼び出すこと。
    """

    def __init__(self, client: GitLabClient, project_path: str) -> None:
        self._client = client
        self._project_path = project_path
        self._project: Any = None
        self._logger = get_logger(__name__)
        self._discussions_cache: LRUCache[int, list[Discussion]] = LRUCache(_CACHE_DISCUSSIONS_MAX)
        self._current_username: str = ""

    async def load(self) -> None:
        """プロジェクト情報を非同期で初期化する。"""
        self._project = await self._client.get_project(self._project_path)
        current_user = await self._client.get_current_user()
        self._current_username = current_user.username
        self._logger.debug("CommentService loaded: project=%s", self._project_path)

    async def get_discussions(self, mr_iid: int) -> list[Discussion]:
        """MRのディスカッション一覧を取得する(キャッシュ対象)。

        システムノート(system=True)は除外する。

        Raises:
            MRNotFoundError: 指定IIDのMRが存在しない場合。
            GitLabConnectionError: API通信エラー。
        """
        cached = self._discussions_cache.get(mr_iid)
        if cached is not None:
            self._logger.debug("Cache hit: discussions iid=%s", mr_iid)
            return cached

        self._logger.debug("Fetching discussions: iid=%s", mr_iid)
        try:
            mr = await asyncio.to_thread(self._project.mergerequests.get, mr_iid, lazy=True)
            raw_discussions = await asyncio.to_thread(mr.discussions.list, all=True)
        except gitlab.exceptions.GitlabGetError as exc:
            if exc.response_code == 404:
                raise MRNotFoundError(f"MR !{mr_iid} が見つかりません。") from exc
            raise GitLabConnectionError("GitLabサーバーとの通信中にエラーが発生しました。") from exc
        except Exception as exc:
            raise self._client._wrap_api_error(exc) from exc

        discussions = [
            d for raw in raw_discussions if (d := self._convert_discussion(raw)) is not None
        ]
        self._discussions_cache.set(mr_iid, discussions)
        return discussions

    async def add_inline_comment(
        self,
        mr_iid: int,
        file_path: str,
        line: int,
        body: str,
        line_type: str,
        old_line: int | None = None,
    ) -> Note:
        """差分行へのインラインコメントを下書きとしてレビューに追加する(Draft Notes API)。

        ブラウザの「レビューを開始」「レビューに追加」と同様、この時点では公開されず、
        publish_review() を呼び出すまで自分だけに見える下書きとして保持される。

        Args:
            mr_iid: MRのプロジェクト内番号。
            file_path: コメント対象のファイルパス(new_path)。
            line: コメント対象の行番号。
            body: コメント本文。
            line_type: "new"(追加行)または "old"(削除行)。
            old_line: ctx行のold側行番号。指定時はnew_line/old_lineの両方をpositionに設定する。

        Raises:
            EmptyCommentError: コメント本文が空または空白のみの場合。
            MRNotFoundError: 指定IIDのMRが存在しない場合。
            GitLabConnectionError: API通信エラー。
        """
        self._validate_body(body)
        self._logger.debug(
            "Adding draft inline comment: iid=%s file=%s line=%s type=%s",
            mr_iid,
            file_path,
            line,
            line_type,
        )
        try:
            mr = await asyncio.to_thread(self._project.mergerequests.get, mr_iid)
            base_sha = mr.diff_refs.get("base_sha", "")
            head_sha = mr.diff_refs.get("head_sha", "")
            start_sha = mr.diff_refs.get("start_sha", "")

            position: dict[str, Any] = {
                "base_sha": base_sha,
                "head_sha": head_sha,
                "start_sha": start_sha,
                "position_type": "text",
                "new_path": file_path,
                "old_path": file_path,
            }
            if line_type == "new":
                position["new_line"] = line
                if old_line is not None:
                    # context (unchanged) line: GitLab requires both new_line and old_line
                    position["old_line"] = old_line
            else:
                position["old_line"] = line
            # line_code is generated server-side by GitLab; do not include it in the request.

            draft = await asyncio.to_thread(
                mr.draft_notes.create, {"note": body, "position": position}
            )
        except gitlab.exceptions.GitlabGetError as exc:
            if exc.response_code == 404:
                raise MRNotFoundError(f"MR !{mr_iid} が見つかりません。") from exc
            raise GitLabConnectionError("GitLabサーバーとの通信中にエラーが発生しました。") from exc
        except Exception as exc:
            raise self._client._wrap_api_error(exc) from exc

        return self._convert_draft_note(draft.attributes)

    async def add_note(self, mr_iid: int, body: str) -> Note:
        """MR全体への下書きコメントをレビューに追加する(Draft Notes API)。

        Raises:
            EmptyCommentError: コメント本文が空または空白のみの場合。
            MRNotFoundError: 指定IIDのMRが存在しない場合。
            GitLabConnectionError: API通信エラー。
        """
        self._validate_body(body)
        self._logger.debug("Adding draft note: iid=%s", mr_iid)
        try:
            mr = await asyncio.to_thread(self._project.mergerequests.get, mr_iid, lazy=True)
            draft = await asyncio.to_thread(mr.draft_notes.create, {"note": body})
        except gitlab.exceptions.GitlabGetError as exc:
            if exc.response_code == 404:
                raise MRNotFoundError(f"MR !{mr_iid} が見つかりません。") from exc
            raise GitLabConnectionError("GitLabサーバーとの通信中にエラーが発生しました。") from exc
        except Exception as exc:
            raise self._client._wrap_api_error(exc) from exc

        return self._convert_draft_note(draft.attributes)

    async def reply_to_discussion(self, mr_iid: int, discussion_id: str, body: str) -> Note:
        """既存ディスカッションへの返信を下書きとしてレビューに追加する(Draft Notes API)。

        Raises:
            EmptyCommentError: コメント本文が空または空白のみの場合。
            MRNotFoundError: 指定IIDのMRが存在しない場合。
            DiscussionNotFoundError: 指定ディスカッションが存在しない場合。
            GitLabConnectionError: API通信エラー。
        """
        self._validate_body(body)
        self._logger.debug("Adding draft reply: iid=%s discussion_id=%s", mr_iid, discussion_id)
        try:
            mr = await asyncio.to_thread(self._project.mergerequests.get, mr_iid, lazy=True)
            # 返信先ディスカッションの存在を検証する(取得できなければ404)
            await asyncio.to_thread(mr.discussions.get, discussion_id)
            draft = await asyncio.to_thread(
                mr.draft_notes.create,
                {"note": body, "in_reply_to_discussion_id": discussion_id},
            )
        except gitlab.exceptions.GitlabGetError as exc:
            if exc.response_code == 404:
                if "discussion" in str(exc).lower():
                    raise DiscussionNotFoundError(
                        f"ディスカッション '{discussion_id}' が見つかりません。"
                    ) from exc
                raise MRNotFoundError(f"MR !{mr_iid} が見つかりません。") from exc
            raise GitLabConnectionError("GitLabサーバーとの通信中にエラーが発生しました。") from exc
        except Exception as exc:
            raise self._client._wrap_api_error(exc) from exc

        return self._convert_draft_note(draft.attributes)

    async def get_draft_notes(self, mr_iid: int) -> list[Note]:
        """現在のレビューの下書きコメント一覧を取得する(自分の下書きのみ、Draft Notes API)。

        Raises:
            MRNotFoundError: 指定IIDのMRが存在しない場合。
            GitLabConnectionError: API通信エラー。
        """
        self._logger.debug("Fetching draft notes: iid=%s", mr_iid)
        try:
            mr = await asyncio.to_thread(self._project.mergerequests.get, mr_iid, lazy=True)
            raw_drafts = await asyncio.to_thread(mr.draft_notes.list, all=True)
        except gitlab.exceptions.GitlabGetError as exc:
            if exc.response_code == 404:
                raise MRNotFoundError(f"MR !{mr_iid} が見つかりません。") from exc
            raise GitLabConnectionError("GitLabサーバーとの通信中にエラーが発生しました。") from exc
        except Exception as exc:
            raise self._client._wrap_api_error(exc) from exc

        return [self._convert_draft_note(d.attributes) for d in raw_drafts]

    async def publish_review(self, mr_iid: int) -> None:
        """下書きコメントを一括公開してレビューを送信する(Draft Notes bulk_publish)。

        ブラウザの「Finish review」相当。公開後は各下書きが通常のディスカッション/
        コメントとして他のメンバーに見えるようになる。

        Raises:
            MRNotFoundError: 指定IIDのMRが存在しない場合。
            GitLabConnectionError: API通信エラー。
        """
        self._logger.debug("Publishing review: iid=%s", mr_iid)
        try:
            mr = await asyncio.to_thread(self._project.mergerequests.get, mr_iid, lazy=True)
            await asyncio.to_thread(mr.draft_notes.bulk_publish)
        except gitlab.exceptions.GitlabGetError as exc:
            if exc.response_code == 404:
                raise MRNotFoundError(f"MR !{mr_iid} が見つかりません。") from exc
            raise GitLabConnectionError("GitLabサーバーとの通信中にエラーが発生しました。") from exc
        except Exception as exc:
            raise self._client._wrap_api_error(exc) from exc

        self._discussions_cache.delete(mr_iid)

    def invalidate_cache(self, mr_iid: int | None = None) -> None:
        """ディスカッションキャッシュを無効化する。mr_iid=Noneで全クリア。"""
        if mr_iid is None:
            self._discussions_cache.clear()
        else:
            self._discussions_cache.delete(mr_iid)

    def _validate_body(self, body: str) -> None:
        """コメント本文のバリデーション。空または空白のみは不可。"""
        if not body or not body.strip():
            raise EmptyCommentError("コメント本文を入力してください。")

    def _convert_discussion(self, raw: Any) -> Discussion | None:
        """python-gitlab Discussion オブジェクトを内部モデルに変換する。

        ユーザーのnoteが1件もない場合はNoneを返す。
        """
        raw_notes = raw.attributes.get("notes", [])
        notes = [self._convert_note(n) for n in raw_notes if not n.get("system", False)]
        if not notes:
            return None
        return Discussion(id=raw.id, notes=notes)

    def _convert_note(self, note_data: dict[str, Any]) -> Note:
        """ノートデータ辞書を内部 Note モデルに変換する。"""
        position = self._convert_position(note_data.get("position"))
        return Note(
            id=note_data.get("id", 0),
            author=note_data.get("author", {}).get("username", ""),
            body=note_data.get("body", ""),
            created_at=note_data.get("created_at", ""),
            position=position,
        )

    def _convert_draft_note(self, data: dict[str, Any]) -> Note:
        """下書きノートデータ辞書を内部 Note モデルに変換する(is_draft=True)。

        Draft Notes API のレスポンスには author 情報が含まれないため、
        接続時に取得した自分のユーザー名を author として設定する。
        """
        position = self._convert_position(data.get("position"))
        return Note(
            id=data.get("id", 0),
            author=self._current_username,
            body=data.get("note", ""),
            created_at=data.get("created_at", ""),
            position=position,
            is_draft=True,
        )

    def _convert_position(self, position_data: dict[str, Any] | None) -> NotePosition | None:
        """ポジションデータ辞書を内部 NotePosition モデルに変換する。"""
        if not position_data:
            return None
        new_line = position_data.get("new_line")
        old_line = position_data.get("old_line")
        if new_line is None and old_line is None:
            return None
        return NotePosition(
            file_path=position_data.get("new_path", ""),
            new_line=new_line,
            old_line=old_line,
        )
