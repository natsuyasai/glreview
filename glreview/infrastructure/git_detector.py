"""gitリポジトリの検出とGitLabプロジェクト情報の抽出。"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from glreview.models import AppConfig, GitLabProjectInfo

# --- カスタム例外 ---


class GitCommandNotFoundError(Exception):
    """git がインストールされていないか、PATHに存在しない。"""


class NotAGitRepositoryError(Exception):
    """作業ディレクトリがgitリポジトリ内にない。"""


class NoRemoteConfiguredError(Exception):
    """このリポジトリにgitリモートが設定されていない。"""


class RemoteNotFoundError(Exception):
    """指定したリモート名が存在しない。"""


class URLParseError(Exception):
    """リモートURLをGitLabプロジェクトパスに解析できない。"""


# --- URLパターン ---

_SSH_STANDARD = re.compile(r"^git@(?P<host>[^:]+):(?P<path>.+?)(?:\.git)?$")
_HTTPS = re.compile(r"^https?://(?P<host>[^/]+)/(?P<path>.+?)(?:\.git)?$")
_SSH_WITH_PORT = re.compile(r"^ssh://git@(?P<host>[^:/]+)(?::\d+)?/(?P<path>.+?)(?:\.git)?$")


class GitRepoDetector:
    """現在のgitリポジトリからGitLabプロジェクトを検出するクラス。"""

    _TIMEOUT = 30  # 秒

    def __init__(self, cwd: Path | None = None) -> None:
        self._cwd = str(cwd) if cwd else None

    def detect(self, config: AppConfig) -> GitLabProjectInfo:
        """gitリモートURLからGitLabProjectInfoを検出して返す。

        Raises:
            GitCommandNotFoundError: gitバイナリが見つからない。
            NotAGitRepositoryError: gitリポジトリ内にない。
            NoRemoteConfiguredError: リモートが設定されていない。
            RemoteNotFoundError: 指定したremote_nameが存在しない。
            URLParseError: リモートURLを解析できない。
        """
        remote_url = self._get_remote_url(config.remote_name)
        host, project_path = self._parse_url(remote_url)
        return GitLabProjectInfo(host=host, project_path=project_path)

    # ------------------------------------------------------------------
    # リモートURL解決
    # ------------------------------------------------------------------

    def _get_remote_url(self, remote_name: str) -> str:
        """選択したリモートのフェッチURLを返す。"""
        if remote_name:
            return self._fetch_url_for(remote_name)

        # フォールバック: origin → 最初に見つかったリモート
        remotes = self._list_remotes()
        if not remotes:
            raise NoRemoteConfiguredError("このリポジトリにはリモートが設定されていません。")

        preferred = "origin" if "origin" in remotes else remotes[0]
        return self._fetch_url_for(preferred)

    def _fetch_url_for(self, remote: str) -> str:
        """指定したリモート名のフェッチURLを返す。"""
        all_remotes = self._list_remotes()
        if remote not in all_remotes:
            raise RemoteNotFoundError(f"リモート '{remote}' が見つかりません。")

        result = self._run_git(["remote", "get-url", remote])
        return result.strip()

    def _list_remotes(self) -> list[str]:
        """設定されているリモート名のリストを返す。"""
        result = self._run_git(["remote"])
        return [r.strip() for r in result.splitlines() if r.strip()]

    # ------------------------------------------------------------------
    # URL解析
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_url(url: str) -> tuple[str, str]:
        """gitリモートURLを解析して(host, project_path)を返す。"""
        for pattern in (_SSH_STANDARD, _HTTPS, _SSH_WITH_PORT):
            m = pattern.match(url.strip())
            if m:
                host = m.group("host")
                path = m.group("path")
                path = _normalize_path(path)
                return host, path

        raise URLParseError(f"リモートURLを解析できません: {url}")

    # ------------------------------------------------------------------
    # subprocessラッパー
    # ------------------------------------------------------------------

    def _run_git(self, args: list[str]) -> str:
        """gitコマンドを実行してstdoutを返す。エラー時は例外を送出する。"""
        cmd = ["git", *args]
        try:
            result = subprocess.run(  # noqa: S603
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=self._TIMEOUT,
                shell=False,
                cwd=self._cwd,
            )
        except FileNotFoundError as exc:
            raise GitCommandNotFoundError(
                "gitコマンドが見つかりません。gitをインストールしてください。"
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise GitCommandNotFoundError(
                f"gitコマンドがタイムアウトしました ({self._TIMEOUT}秒)。"
            ) from exc

        if result.returncode != 0:
            stderr_lower = result.stderr.lower()
            if "not a git repository" in stderr_lower:
                raise NotAGitRepositoryError("gitリポジトリ内で実行してください。")
            # 汎用gitエラー — stderrをユーザー向けメッセージに含めない(SECURITY-09)
            raise subprocess.CalledProcessError(
                result.returncode,
                cmd,
                result.stdout,
                result.stderr,
            )

        return result.stdout


def _normalize_path(path: str) -> str:
    """.gitサフィックスと先頭/末尾のスラッシュを除去する。"""
    path = path.removesuffix(".git")
    path = path.strip("/")
    return path
