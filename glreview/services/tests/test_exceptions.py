"""glreview.services.exceptions のユニットテスト。"""

import pytest

from glreview.services.exceptions import (
    DiscussionNotFoundError,
    EmptyCommentError,
    FileNotFoundInMRError,
    GitLabAccessDeniedError,
    GitLabAuthError,
    GitLabConnectionError,
    GitLabProjectNotFoundError,
    GLReviewAPIError,
    MRNotFoundError,
)


class TestGLReviewAPIError:
    def test_message_stored(self) -> None:
        err = GLReviewAPIError("test message")
        assert err.message == "test message"

    def test_is_exception(self) -> None:
        err = GLReviewAPIError("msg")
        assert isinstance(err, Exception)


class TestSubclasses:
    @pytest.mark.parametrize(
        "exc_class",
        [
            GitLabAuthError,
            GitLabConnectionError,
            GitLabProjectNotFoundError,
            GitLabAccessDeniedError,
            MRNotFoundError,
            FileNotFoundInMRError,
            DiscussionNotFoundError,
            EmptyCommentError,
        ],
    )
    def test_inherits_base(self, exc_class: type) -> None:
        err = exc_class("msg")
        assert isinstance(err, GLReviewAPIError)
        assert err.message == "msg"

    def test_gitlab_auth_error_catchable_as_base(self) -> None:
        with pytest.raises(GLReviewAPIError):
            raise GitLabAuthError("auth failed")
