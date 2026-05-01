"""glreview.infrastructure.git_ops のユニットテスト。"""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from glreview.infrastructure.git_ops import (
    CheckoutResult,
    GitOpsError,
    _run_git,
    checkout_or_switch_branch,
)


class TestRunGit:
    def test_success_returns_stdout(self) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "main\n"
        mock_result.stderr = ""
        with patch("subprocess.run", return_value=mock_result):
            result = _run_git(["branch", "--show-current"])
        assert result == "main\n"

    def test_nonzero_returncode_raises(self) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "error: something failed"
        with patch("subprocess.run", return_value=mock_result):
            with pytest.raises(GitOpsError) as exc_info:
                _run_git(["checkout", "nonexistent"])
        assert "error: something failed" in str(exc_info.value)

    def test_nonzero_no_stderr_uses_default_message(self) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = ""
        with patch("subprocess.run", return_value=mock_result):
            with pytest.raises(GitOpsError) as exc_info:
                _run_git(["status"])
        assert "git コマンドが失敗しました" in str(exc_info.value)

    def test_file_not_found_raises_git_ops_error(self) -> None:
        with patch("subprocess.run", side_effect=FileNotFoundError):
            with pytest.raises(GitOpsError) as exc_info:
                _run_git(["status"])
        assert "git コマンドが見つかりません" in str(exc_info.value)

    def test_timeout_raises_git_ops_error(self) -> None:
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="git", timeout=30)):
            with pytest.raises(GitOpsError) as exc_info:
                _run_git(["status"])
        assert "タイムアウト" in str(exc_info.value)

    def test_stderr_is_stored_on_error(self) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "stderr content"
        with patch("subprocess.run", return_value=mock_result):
            with pytest.raises(GitOpsError) as exc_info:
                _run_git(["status"])
        assert exc_info.value.stderr == "stderr content"


class TestGitOpsError:
    def test_message_is_set(self) -> None:
        err = GitOpsError("something went wrong")
        assert str(err) == "something went wrong"

    def test_stderr_defaults_to_empty_string(self) -> None:
        err = GitOpsError("msg")
        assert err.stderr == ""

    def test_stderr_can_be_set(self) -> None:
        err = GitOpsError("msg", stderr="some error")
        assert err.stderr == "some error"


class TestCheckoutOrSwitchBranch:
    def _make_run_git_responses(self, current: str, local_branches: str, *extra: str):
        """_run_git の連続した戻り値を設定する。"""
        responses = [current, local_branches, *extra]
        call_iter = iter(responses)
        return lambda *args, **kwargs: next(call_iter)

    def test_checkout_new_branch(self) -> None:
        """ローカルに存在しないブランチをチェックアウトする。"""
        responses = iter(["main\n", "", ""])  # current, local_list, checkout output
        with patch(
            "glreview.infrastructure.git_ops._run_git",
            side_effect=lambda *a, **kw: next(responses),
        ):
            result = checkout_or_switch_branch("feature/new", "origin")
        assert result.action == "checkout"
        assert result.branch == "feature/new"
        assert "チェックアウト" in result.message

    def test_pull_when_already_on_branch(self) -> None:
        """既に対象ブランチにいる場合はpullを実行する。"""
        responses = iter(
            [
                "feature/existing\n",  # current branch
                "  feature/existing\n",  # local list - branch exists
                "",  # set-upstream-to
                "",  # pull
            ]
        )
        with patch(
            "glreview.infrastructure.git_ops._run_git",
            side_effect=lambda *a, **kw: next(responses),
        ):
            result = checkout_or_switch_branch("feature/existing", "origin")
        assert result.action == "pull"
        assert result.branch == "feature/existing"
        assert "最新変更" in result.message

    def test_switch_when_on_different_branch(self) -> None:
        """別ブランチにいるがローカルにはある場合はswitchを実行する。"""
        responses = iter(
            [
                "main\n",  # current branch
                "  feature/other\n",  # local list - branch exists
                "",  # switch
                "",  # set-upstream-to
                "",  # pull
            ]
        )
        with patch(
            "glreview.infrastructure.git_ops._run_git",
            side_effect=lambda *a, **kw: next(responses),
        ):
            result = checkout_or_switch_branch("feature/other", "origin")
        assert result.action == "switch"
        assert result.branch == "feature/other"
        assert "スイッチ" in result.message

    def test_error_propagates(self) -> None:
        """_run_git が失敗した場合は GitOpsError が伝播する。"""
        with patch(
            "glreview.infrastructure.git_ops._run_git",
            side_effect=GitOpsError("fatal: no branch"),
        ):
            with pytest.raises(GitOpsError):
                checkout_or_switch_branch("feature/fail", "origin")


class TestCheckoutResult:
    def test_fields(self) -> None:
        result = CheckoutResult(branch="main", action="checkout", message="done")
        assert result.branch == "main"
        assert result.action == "checkout"
        assert result.message == "done"
