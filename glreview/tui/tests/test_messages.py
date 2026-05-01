"""tui/messages.py のユニットテスト。"""

from __future__ import annotations

from glreview.tui.messages import CommentPosted, ShowDiff, ShowOverview


class TestShowOverview:
    def test_mr_iid_is_set(self) -> None:
        msg = ShowOverview(mr_iid=42)
        assert msg.mr_iid == 42

    def test_different_iid(self) -> None:
        msg = ShowOverview(mr_iid=1)
        assert msg.mr_iid == 1


class TestShowDiff:
    def test_mr_iid_and_file_path_are_set(self) -> None:
        msg = ShowDiff(mr_iid=7, file_path="src/main.py")
        assert msg.mr_iid == 7
        assert msg.file_path == "src/main.py"

    def test_different_values(self) -> None:
        msg = ShowDiff(mr_iid=100, file_path="tests/test_foo.py")
        assert msg.mr_iid == 100
        assert msg.file_path == "tests/test_foo.py"


class TestCommentPosted:
    def test_mr_iid_is_set(self) -> None:
        msg = CommentPosted(mr_iid=5)
        assert msg.mr_iid == 5
