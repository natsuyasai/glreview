"""glreview の設定管理。"""

from __future__ import annotations

import os
import sys
import tomllib
from pathlib import Path
from typing import Any

from glreview.models import AppConfig

_VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
_VALID_THEMES = {"dark", "light", "textual-dark", "textual-light", "nord", "gruvbox"}
_TOKEN_PLACEHOLDERS = {"your-token-here", "xxx", "xxxx", "placeholder", "changeme"}

_DEFAULT_CONFIG_TEMPLATE = """\
[gitlab]
url = "{gitlab_url}"
ssl_verify = true

[auth]
token = "{token}"

[editor]
command = "{editor}"
# terminal = "xterm -e"  # open editor in new terminal (auto-detected if omitted)

[logging]
level = "INFO"

[appearance]
theme = "dark"
pygments_style = ""

[git]
remote_name = ""
"""


def _default_config_path() -> Path:
    xdg = os.environ.get("XDG_CONFIG_HOME", "")
    if xdg:
        base = Path(xdg)
    else:
        base = Path.home() / ".config"
    return base / "glreview" / "config.toml"


class ConfigError(Exception):
    """設定が無効または存在しない場合に発生する例外。"""


class ConfigManager:
    """アプリケーション設定の読み込み・検証・書き込みを管理するクラス。"""

    def __init__(self, config_path: Path | None = None) -> None:
        self._config_path: Path = config_path or _default_config_path()

    @property
    def config_path(self) -> Path:
        return self._config_path

    # ------------------------------------------------------------------
    # 公開API
    # ------------------------------------------------------------------

    def load(self) -> AppConfig:
        """設定ファイルを読み込む。ファイルが存在しない場合はセットアップウィザードを実行する。"""
        if not self._config_path.exists():
            return self._run_setup_wizard()

        try:
            raw = self._read_toml(self._config_path)
        except tomllib.TOMLDecodeError as exc:
            print(
                f"Configuration file parse error: {exc}\n"
                "Please run the setup wizard to recreate the configuration file.",
                file=sys.stderr,
            )
            choice = input("Run setup wizard? [y/N]: ").strip().lower()
            if choice == "y":
                return self._run_setup_wizard()
            sys.exit(1)

        return self._map_to_config(raw)

    def generate_default(self, gitlab_url: str, token: str, editor: str) -> str:
        """指定した値でTOML文字列を生成して返す。"""
        return _DEFAULT_CONFIG_TEMPLATE.format(
            gitlab_url=gitlab_url,
            token=token,
            editor=editor,
        )

    # ------------------------------------------------------------------
    # バリデーション
    # ------------------------------------------------------------------

    def validate(self, config: AppConfig) -> list[str]:
        """バリデーションエラーのリストを返す(空リスト = 有効)。"""
        errors: list[str] = []
        errors.extend(self._validate_gitlab_url(config.gitlab_url))
        errors.extend(self._validate_token(config.token))
        errors.extend(self._validate_log_level(config.log_level))
        errors.extend(self._validate_theme(config.theme))
        return errors

    @staticmethod
    def _validate_gitlab_url(url: str) -> list[str]:
        if not url:
            return ["GitLab URLは必須です"]
        if not (url.startswith("http://") or url.startswith("https://")):
            return ["GitLab URLはhttp://またはhttps://で始まる必要があります"]
        return []

    @staticmethod
    def _validate_token(token: str) -> list[str]:
        if not token:
            return ["アクセストークンは必須です"]
        if token.lower() in _TOKEN_PLACEHOLDERS:
            return ["アクセストークンにプレースホルダー値が設定されています"]
        return []

    @staticmethod
    def _validate_log_level(level: str) -> list[str]:
        if level.upper() not in _VALID_LOG_LEVELS:
            return [f"無効なログレベルです: {level}"]
        return []

    @staticmethod
    def _validate_theme(theme: str) -> list[str]:
        if theme not in _VALID_THEMES:
            return [f"無効なテーマ名です: {theme}"]
        return []

    # ------------------------------------------------------------------
    # 内部ヘルパー
    # ------------------------------------------------------------------

    def _map_to_config(self, raw: dict[str, Any]) -> AppConfig:
        gitlab_section = raw.get("gitlab", {})
        auth_section = raw.get("auth", {})
        editor_section = raw.get("editor", {})
        logging_section = raw.get("logging", {})
        appearance_section = raw.get("appearance", {})
        git_section = raw.get("git", {})

        default_editor = os.environ.get("EDITOR", "vi")

        config = AppConfig(
            gitlab_url=gitlab_section.get("url", "https://gitlab.com"),
            token=auth_section.get("token", ""),
            editor=editor_section.get("command", default_editor),
            terminal=editor_section.get("terminal", ""),
            log_level=logging_section.get("level", "INFO").upper(),
            theme=appearance_section.get("theme", "dark"),
            remote_name=git_section.get("remote_name", ""),
            ssl_verify=gitlab_section.get("ssl_verify", True),
            pygments_style=appearance_section.get("pygments_style", ""),
        )

        errors = self.validate(config)
        if errors:
            # SECURITY-09: ユーザー向けメッセージのみ表示し、内部詳細は含めない
            for err in errors:
                print(f"設定エラー: {err}", file=sys.stderr)
            raise ConfigError("設定ファイルに問題があります。config.tomlを確認してください。")

        if config.token and not config.token.startswith("glpat-"):
            print(
                "警告: GitLabトークンは通常glpat-で始まります",
                file=sys.stderr,
            )

        return config

    def save_setting(self, section: str, key: str, value: str) -> None:
        """設定ファイルの指定セクション・キーの値を更新して保存する。

        該当のキーが存在しない場合はセクション末尾に追加する。
        """
        if not self._config_path.exists():
            return

        text = self._config_path.read_text(encoding="utf-8")
        lines = text.splitlines(keepends=True)

        # value を TOML 値として文字列化する（bool/str 対応）
        if isinstance(value, bool):
            toml_value = "true" if value else "false"
        else:
            toml_value = f'"{value}"'

        import re

        # セクション内でキーを探して置換する
        in_section = False
        key_pattern = re.compile(rf"^\s*{re.escape(key)}\s*=")
        section_pattern = re.compile(rf"^\s*\[{re.escape(section)}\]")
        next_section_pattern = re.compile(r"^\s*\[")

        new_lines: list[str] = []
        key_written = False

        for _i, line in enumerate(lines):
            if section_pattern.match(line):
                in_section = True
                new_lines.append(line)
                continue
            if in_section:
                if next_section_pattern.match(line) and not section_pattern.match(line):
                    # セクションが終わった — キーがまだ書かれていなければここに挿入
                    if not key_written:
                        new_lines.append(f"{key} = {toml_value}\n")
                        key_written = True
                    in_section = False
                elif key_pattern.match(line):
                    new_lines.append(f"{key} = {toml_value}\n")
                    key_written = True
                    continue
            new_lines.append(line)

        # セクションが最後まで続いていてキーが未書き込みの場合は末尾に追加
        if not key_written:
            new_lines.append(f"{key} = {toml_value}\n")

        self._write_config("".join(new_lines))

    @staticmethod
    def _read_toml(path: Path) -> dict[str, Any]:
        with path.open("rb") as f:
            return tomllib.load(f)

    def _write_config(self, content: str) -> None:
        config_dir = self._config_path.parent
        config_dir.mkdir(parents=True, exist_ok=True)

        if os.name != "nt":
            os.chmod(config_dir, 0o700)

        self._config_path.write_text(content, encoding="utf-8")

        if os.name != "nt":
            os.chmod(self._config_path, 0o600)

    def _run_setup_wizard(self) -> AppConfig:
        """設定ファイルを作成するための対話型セットアップウィザード。"""
        print("=" * 60)
        print("glreview セットアップウィザード")
        print("=" * 60)
        print(f"設定ファイルが見つかりません: {self._config_path.name}")
        print("設定を入力してください。\n")

        while True:
            gitlab_url = input("GitLab URL [https://gitlab.com]: ").strip() or "https://gitlab.com"

            url_errors = self._validate_gitlab_url(gitlab_url)
            if url_errors:
                for err in url_errors:
                    print(f"エラー: {err}")
                continue
            break

        while True:
            print("アクセストークン (glpat-...): ", end="", flush=True)
            token = input().strip()
            token_errors = self._validate_token(token)
            if token_errors:
                for err in token_errors:
                    print(f"エラー: {err}")
                continue

            # 接続テスト
            print("接続テスト中...")
            if self._test_connection(gitlab_url, token):
                print("接続成功!")
                break
            else:
                print("接続に失敗しました。URLとトークンを確認してください。")

        default_editor = os.environ.get("EDITOR", "vi")
        editor = input(f"外部エディタコマンド [{default_editor}]: ").strip() or default_editor

        content = self.generate_default(gitlab_url, token, editor)
        self._write_config(content)
        print(f"\n設定ファイルを保存しました: {self._config_path.name}")
        print("=" * 60 + "\n")

        raw = tomllib.loads(content)
        return self._map_to_config(raw)

    @staticmethod
    def _test_connection(gitlab_url: str, token: str) -> bool:
        """GitLab APIへの接続テスト。成功時はTrueを返す。"""
        try:
            import gitlab

            gl = gitlab.Gitlab(gitlab_url, private_token=token)
            gl.auth()
            return True
        except Exception:
            return False
