"""glreview.infrastructure.git_detector のユニットテスト。"""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from glreview.infrastructure.git_detector import (
    GitCommandNotFoundError,
    GitRepoDetector,
    NoRemoteConfiguredError,
    NotAGitRepositoryError,
    RemoteNotFoundError,
    URLParseError,
    _normalize_path,
)
from glreview.models import AppConfig


def _config(remote_name: str = "") -> AppConfig:
    return AppConfig(
        gitlab_url="https://gitlab.com",
        token="glpat-test",
        remote_name=remote_name,
    )


class TestURLParsing:
    """GitRepoDetector._parse_url のテスト(静的メソッド、subprocessなし)。"""

    def test_標準SSH形式のURLを解析する(self):
        host, path = GitRepoDetector._parse_url("git@gitlab.com:group/project.git")
        assert host == "gitlab.com"
        assert path == "group/project"

    def test_サブグループを含む標準SSH形式のURLを解析する(self):
        host, path = GitRepoDetector._parse_url("git@gitlab.com:group/sub1/sub2/project.git")
        assert host == "gitlab.com"
        assert path == "group/sub1/sub2/project"

    def test_HTTPS形式のURLを解析する(self):
        host, path = GitRepoDetector._parse_url("https://gitlab.com/group/project.git")
        assert host == "gitlab.com"
        assert path == "group/project"

    def test_git拡張子なしのHTTPS_URLを解析する(self):
        host, path = GitRepoDetector._parse_url("https://gitlab.com/group/project")
        assert host == "gitlab.com"
        assert path == "group/project"

    def test_ポート番号付きSSH形式のURLを解析する(self):
        host, path = GitRepoDetector._parse_url(
            "ssh://git@gitlab.example.com:2222/group/project.git"
        )
        assert host == "gitlab.example.com"
        assert path == "group/project"

    def test_カスタムホストのURLを解析する(self):
        host, path = GitRepoDetector._parse_url("git@self-hosted.example.com:company/repo.git")
        assert host == "self-hosted.example.com"
        assert path == "company/repo"

    def test_解析できないURLでURLParseErrorが発生する(self):
        with pytest.raises(URLParseError):
            GitRepoDetector._parse_url("not-a-git-url")

    def test_前後の空白は無視される(self):
        host, path = GitRepoDetector._parse_url("  https://gitlab.com/group/project.git  ")
        assert host == "gitlab.com"
        assert path == "group/project"


class TestNormalizePath:
    def test_git拡張子が除去される(self):
        assert _normalize_path("group/project.git") == "group/project"

    def test_先頭スラッシュが除去される(self):
        assert _normalize_path("/group/project") == "group/project"

    def test_末尾スラッシュが除去される(self):
        assert _normalize_path("group/project/") == "group/project"

    def test_サブグループパスが保持される(self):
        assert _normalize_path("g/s1/s2/p.git") == "g/s1/s2/p"


class TestGitRepoDetectorWithMocks:
    """subprocessをモックしたテスト。"""

    def _detector(self) -> GitRepoDetector:
        return GitRepoDetector()

    def _mock_run(self, detector: GitRepoDetector, side_effects: dict[tuple, str]):
        """_run_gitを引数タプルで指定した戻り値に差し替える。"""

        def fake_run(args):
            key = tuple(args)
            for k, v in side_effects.items():
                if key == k:
                    if isinstance(v, Exception):
                        raise v
                    return v
            raise AssertionError(f"Unexpected git args: {args}")

        return patch.object(detector, "_run_git", side_effect=fake_run)

    def test_originリモートを使用して検出する(self):
        detector = self._detector()
        effects = {
            ("remote",): "origin\n",
            ("remote", "get-url", "origin"): "git@gitlab.com:group/project.git\n",
        }
        with self._mock_run(detector, effects):
            info = detector.detect(_config())
        assert info.host == "gitlab.com"
        assert info.project_path == "group/project"

    def test_originがない場合は最初のリモートを使用する(self):
        detector = self._detector()
        effects = {
            ("remote",): "upstream\n",
            ("remote", "get-url", "upstream"): "https://gitlab.com/group/proj.git\n",
        }
        with self._mock_run(detector, effects):
            info = detector.detect(_config())
        assert info.project_path == "group/proj"

    def test_設定したリモート名を使用する(self):
        detector = self._detector()
        effects = {
            ("remote",): "origin\nmy-remote\n",
            ("remote", "get-url", "my-remote"): ("git@gitlab.com:company/repo.git\n"),
        }
        with self._mock_run(detector, effects):
            info = detector.detect(_config(remote_name="my-remote"))
        assert info.project_path == "company/repo"

    def test_リモートが未設定の場合NoRemoteConfiguredErrorが発生する(self):
        detector = self._detector()
        effects = {("remote",): ""}
        with self._mock_run(detector, effects):
            with pytest.raises(NoRemoteConfiguredError):
                detector.detect(_config())

    def test_設定したリモートが存在しない場合RemoteNotFoundErrorが発生する(self):
        detector = self._detector()
        effects = {("remote",): "origin\n"}
        with self._mock_run(detector, effects):
            with pytest.raises(RemoteNotFoundError):
                detector.detect(_config(remote_name="nonexistent"))

    def test_gitが見つからない場合GitCommandNotFoundErrorが発生する(self):
        detector = self._detector()
        with patch.object(
            detector,
            "_run_git",
            side_effect=GitCommandNotFoundError("git not found"),
        ):
            with pytest.raises(GitCommandNotFoundError):
                detector.detect(_config())

    def test_gitリポジトリでない場合NotAGitRepositoryErrorが発生する(self):
        detector = self._detector()
        with patch.object(
            detector,
            "_run_git",
            side_effect=NotAGitRepositoryError("not a git repo"),
        ):
            with pytest.raises(NotAGitRepositoryError):
                detector.detect(_config())


class TestRunGitErrors:
    """_run_git のエラーマッピングのテスト。"""

    def test_FileNotFoundErrorでGitCommandNotFoundErrorが発生する(self):
        detector = GitRepoDetector()
        with patch("subprocess.run", side_effect=FileNotFoundError):
            with pytest.raises(GitCommandNotFoundError):
                detector._run_git(["--version"])

    def test_タイムアウト時にGitCommandNotFoundErrorが発生する(self):
        detector = GitRepoDetector()
        with patch(
            "subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd=["git"], timeout=30),
        ):
            with pytest.raises(GitCommandNotFoundError):
                detector._run_git(["--version"])

    def test_gitリポジトリエラーのstderrでNotAGitRepositoryErrorが発生する(self):
        detector = GitRepoDetector()
        result = MagicMock()
        result.returncode = 128
        result.stdout = ""
        result.stderr = "fatal: not a git repository"
        with patch("subprocess.run", return_value=result):
            with pytest.raises(NotAGitRepositoryError):
                detector._run_git(["rev-parse", "--git-dir"])

    def test_汎用エラー時にCalledProcessErrorが発生する(self):
        detector = GitRepoDetector()
        result = MagicMock()
        result.returncode = 1
        result.stdout = ""
        result.stderr = "some other error"
        with patch("subprocess.run", return_value=result):
            with pytest.raises(subprocess.CalledProcessError):
                detector._run_git(["remote"])
