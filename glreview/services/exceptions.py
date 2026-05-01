"""GitLab API サービス層のカスタム例外クラス。"""

from __future__ import annotations


class GLReviewAPIError(Exception):
    """API層の基底エラー。ユーザー向けメッセージを保持する。"""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class GitLabAuthError(GLReviewAPIError):
    """GitLab認証失敗(401)。"""


class GitLabConnectionError(GLReviewAPIError):
    """GitLabサーバーへの接続失敗またはタイムアウト。"""


class GitLabProjectNotFoundError(GLReviewAPIError):
    """指定されたGitLabプロジェクトが見つからない(404)。"""


class GitLabAccessDeniedError(GLReviewAPIError):
    """GitLabリソースへのアクセス権限がない(403)。"""


class MRNotFoundError(GLReviewAPIError):
    """指定されたMRが見つからない。"""


class FileNotFoundInMRError(GLReviewAPIError):
    """MR内に指定されたファイルが見つからない。"""


class DiscussionNotFoundError(GLReviewAPIError):
    """指定されたディスカッションが見つからない。"""


class EmptyCommentError(GLReviewAPIError):
    """コメント本文が空または空白のみ。"""
