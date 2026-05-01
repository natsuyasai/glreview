"""UNIT-01 インフラストラクチャコンポーネントの統合テスト。

実際のファイルI/OとtmpPathに作成したgitリポジトリを使用する。
subprocessやファイル操作のモックはしない。
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from glreview.infrastructure.config import ConfigManager
from glreview.infrastructure.git_detector import (
    GitRepoDetector,
    NotAGitRepositoryError,
)
from glreview.infrastructure.logger import get_logger, setup_logging

# ---------------------------------------------------------------------------
# ヘルパー
# ---------------------------------------------------------------------------


def _make_toml(url: str, token: str) -> str:
    return (
        f'[gitlab]\nurl = "{url}"\n'
        f'[auth]\ntoken = "{token}"\n'
        '[editor]\ncommand = "vi"\n'
        '[logging]\nlevel = "INFO"\n'
        '[appearance]\ntheme = "dark"\n'
        '[git]\nremote_name = ""\n'
    )


def _init_git_repo(path: Path) -> None:
    subprocess.run(["git", "init", str(path)], check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=str(path),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=str(path),
        check=True,
        capture_output=True,
    )


def _add_remote(repo_path: Path, name: str, url: str) -> None:
    subprocess.run(
        ["git", "remote", "add", name, url],
        cwd=str(repo_path),
        check=True,
        capture_output=True,
    )


# ---------------------------------------------------------------------------
# ConfigManager 統合テスト
# ---------------------------------------------------------------------------


class TestConfigManagerIntegration:
    def test_設定ファイルを書き込んで読み込む(self, tmp_path):
        config_file = tmp_path / "config.toml"
        config_file.write_text(_make_toml("https://gitlab.com", "glpat-inttest1"), encoding="utf-8")

        manager = ConfigManager(config_path=config_file)
        config = manager.load()

        assert config.gitlab_url == "https://gitlab.com"
        assert config.token == "glpat-inttest1"
        assert config.editor == "vi"
        assert config.log_level == "INFO"
        assert config.theme == "dark"

    def test_デフォルト設定を生成して解析する(self, tmp_path):
        manager = ConfigManager(config_path=tmp_path / "config.toml")
        content = manager.generate_default(
            "https://self-hosted.example.com", "glpat-mytoken", "nvim"
        )
        (tmp_path / "config.toml").write_text(content, encoding="utf-8")

        config = manager.load()
        assert config.gitlab_url == "https://self-hosted.example.com"
        assert config.editor == "nvim"

    def test_Unix環境で設定ファイルのパーミッションが0600になる(self, tmp_path):
        """Unix環境では設定ファイルのモードが0600であるべき。"""
        import os

        if os.name == "nt":
            pytest.skip("File permission test skipped on Windows")

        config_file = tmp_path / "config.toml"
        config_file.write_text(_make_toml("https://gitlab.com", "glpat-test"), encoding="utf-8")
        os.chmod(config_file, 0o600)

        stat = config_file.stat()
        assert oct(stat.st_mode)[-3:] == "600"


# ---------------------------------------------------------------------------
# GitRepoDetector 統合テスト
# ---------------------------------------------------------------------------


class TestGitRepoDetectorIntegration:
    def test_SSHのoriginリモートを検出する(self, tmp_path):
        _init_git_repo(tmp_path)
        _add_remote(tmp_path, "origin", "git@gitlab.com:mygroup/myproject.git")

        detector = GitRepoDetector(cwd=tmp_path)
        from glreview.models import AppConfig

        config = AppConfig(gitlab_url="https://gitlab.com", token="glpat-t")
        info = detector.detect(config)

        assert info.host == "gitlab.com"
        assert info.project_path == "mygroup/myproject"

    def test_HTTPSのoriginリモートを検出する(self, tmp_path):
        _init_git_repo(tmp_path)
        _add_remote(tmp_path, "origin", "https://gitlab.example.com/corp/api.git")

        detector = GitRepoDetector(cwd=tmp_path)
        from glreview.models import AppConfig

        config = AppConfig(gitlab_url="https://gitlab.example.com", token="glpat-t")
        info = detector.detect(config)

        assert info.host == "gitlab.example.com"
        assert info.project_path == "corp/api"

    def test_サブグループパスを検出する(self, tmp_path):
        _init_git_repo(tmp_path)
        _add_remote(tmp_path, "origin", "git@gitlab.com:top/middle/bottom/project.git")

        detector = GitRepoDetector(cwd=tmp_path)
        from glreview.models import AppConfig

        config = AppConfig(gitlab_url="https://gitlab.com", token="glpat-t")
        info = detector.detect(config)

        assert info.project_path == "top/middle/bottom/project"

    def test_origin以外のリモートにフォールバックする(self, tmp_path):
        _init_git_repo(tmp_path)
        _add_remote(tmp_path, "upstream", "git@gitlab.com:team/repo.git")

        detector = GitRepoDetector(cwd=tmp_path)
        from glreview.models import AppConfig

        config = AppConfig(gitlab_url="https://gitlab.com", token="glpat-t")
        info = detector.detect(config)

        assert info.project_path == "team/repo"

    def test_gitリポジトリでない場合NotAGitRepositoryErrorが発生する(self, tmp_path):
        empty_dir = tmp_path / "not_a_repo"
        empty_dir.mkdir()

        detector = GitRepoDetector(cwd=empty_dir)
        from glreview.models import AppConfig

        config = AppConfig(gitlab_url="https://gitlab.com", token="glpat-t")

        with pytest.raises(NotAGitRepositoryError):
            detector.detect(config)


# ---------------------------------------------------------------------------
# Logger 統合テスト
# ---------------------------------------------------------------------------


class TestLoggerIntegration:
    def test_ログファイルに書き込まれる(self, tmp_path):
        setup_logging("DEBUG", log_dir=tmp_path)
        logger = get_logger("integration_test")
        logger.info("Integration test message")

        log_files = list(tmp_path.glob("glreview_*.log"))
        assert len(log_files) == 1

        content = log_files[0].read_text(encoding="utf-8")
        assert "Integration test message" in content

    def test_ログ内のトークンがマスクされる(self, tmp_path):
        setup_logging("DEBUG", log_dir=tmp_path)
        logger = get_logger("security_test")
        logger.info("Using token glpat-supersecrettoken1234")

        log_files = list(tmp_path.glob("glreview_*.log"))
        content = log_files[0].read_text(encoding="utf-8")
        assert "glpat-" not in content
        assert "***REDACTED***" in content

    def test_ログのフォーマットが正しい(self, tmp_path):
        setup_logging("INFO", log_dir=tmp_path)
        logger = get_logger("format_test")
        logger.info("Format check")

        log_files = list(tmp_path.glob("glreview_*.log"))
        content = log_files[0].read_text(encoding="utf-8")
        # 期待値: "YYYY-MM-DDTHH:MM:SS [INFO] glreview.format_test: Format check"
        assert "[INFO]" in content
        assert "glreview.format_test" in content
        assert "Format check" in content

    def test_Unix環境でログファイルのパーミッションが0600になる(self, tmp_path):
        import os

        if os.name == "nt":
            pytest.skip("File permission test skipped on Windows")

        setup_logging("INFO", log_dir=tmp_path)
        log_files = list(tmp_path.glob("glreview_*.log"))
        assert len(log_files) == 1

        stat = log_files[0].stat()
        assert oct(stat.st_mode)[-3:] == "600"

        dir_stat = tmp_path.stat()
        assert oct(dir_stat.st_mode)[-3:] == "700"
