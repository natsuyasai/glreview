"""git ブランチ操作ユーティリティ。"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

_TIMEOUT = 30  # 秒


class GitOpsError(Exception):
    """git 操作に失敗した際の例外。"""

    def __init__(self, message: str, stderr: str = "") -> None:
        super().__init__(message)
        self.stderr = stderr


@dataclass
class CheckoutResult:
    """checkout/switch 操作の結果。"""

    branch: str
    action: str  # "checkout" | "switch" | "pull"
    message: str


def _run_git(args: list[str], cwd: Path | None = None) -> str:
    """git コマンドを実行し stdout を返す。失敗時は GitOpsError を送出する。"""
    cmd = ["git", *args]
    try:
        result = subprocess.run(  # noqa: S603
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=_TIMEOUT,
            shell=False,
            cwd=cwd,
        )
    except FileNotFoundError as exc:
        raise GitOpsError("git コマンドが見つかりません。") from exc
    except subprocess.TimeoutExpired as exc:
        raise GitOpsError(f"git コマンドがタイムアウトしました ({_TIMEOUT}秒)。") from exc

    if result.returncode != 0:
        msg = result.stderr.strip() or "git コマンドが失敗しました。"
        raise GitOpsError(msg, stderr=result.stderr)

    return result.stdout


def checkout_or_switch_branch(branch: str, remote: str, cwd: Path | None = None) -> CheckoutResult:
    """マージリクエストのソースブランチをチェックアウトまたはスイッチする。

    - ローカルに存在しない場合: ``git checkout -b <branch> --track <remote>/<branch>``
    - 既にチェックアウト済みの場合: upstream を設定して ``git pull``
    - ローカルに存在するが別ブランチの場合: ``git switch <branch>`` → upstream 設定 → ``git pull``

    Args:
        branch: チェックアウト対象のブランチ名。
        remote: リモート名 (例: "origin")。
        cwd: git コマンドを実行するディレクトリ。None の場合はカレントディレクトリ。

    Returns:
        CheckoutResult: 操作内容と結果メッセージ。

    Raises:
        GitOpsError: git コマンドが失敗した場合。
    """
    # 現在のブランチを取得
    current_branch = _run_git(["branch", "--show-current"], cwd=cwd).strip()

    # ローカルにブランチが存在するか確認
    local_list = _run_git(["branch", "--list", branch], cwd=cwd).strip()
    branch_exists_locally = bool(local_list)

    remote_ref = f"{remote}/{branch}"

    if not branch_exists_locally:
        # ローカルに存在しない → チェックアウトして upstream を設定
        _run_git(["checkout", "-b", branch, "--track", remote_ref], cwd=cwd)
        return CheckoutResult(
            branch=branch,
            action="checkout",
            message=f"'{branch}' をチェックアウトしました (upstream: {remote_ref})",
        )

    if current_branch == branch:
        # 既にこのブランチにいる → upstream を設定して pull
        _run_git(["branch", f"--set-upstream-to={remote_ref}", branch], cwd=cwd)
        _run_git(["pull"], cwd=cwd)
        return CheckoutResult(
            branch=branch,
            action="pull",
            message=f"'{branch}' の最新変更を取得しました (upstream: {remote_ref})",
        )

    # 別ブランチだがローカルに存在する → スイッチして upstream 設定・pull
    _run_git(["switch", branch], cwd=cwd)
    _run_git(["branch", f"--set-upstream-to={remote_ref}", branch], cwd=cwd)
    _run_git(["pull"], cwd=cwd)
    return CheckoutResult(
        branch=branch,
        action="switch",
        message=f"'{branch}' にスイッチして最新変更を取得しました (upstream: {remote_ref})",
    )
