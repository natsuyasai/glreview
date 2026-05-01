"""glreview.infrastructure.config のユニットテスト。"""

from __future__ import annotations

import tomllib
from pathlib import Path
from unittest.mock import patch

import pytest

from glreview.infrastructure.config import ConfigError, ConfigManager
from glreview.models import AppConfig


def _make_toml(
    url: str = "https://gitlab.com",
    token: str = "glpat-validtoken",
    editor: str = "vi",
    log_level: str = "INFO",
    theme: str = "dark",
    remote_name: str = "",
) -> str:
    return (
        f'[gitlab]\nurl = "{url}"\n'
        f'[auth]\ntoken = "{token}"\n'
        f'[editor]\ncommand = "{editor}"\n'
        f'[logging]\nlevel = "{log_level}"\n'
        f'[appearance]\ntheme = "{theme}"\n'
        f'[git]\nremote_name = "{remote_name}"\n'
    )


class TestConfigManagerLoad:
    def test_有効な設定ファイルをロードする(self, tmp_path):
        config_file = tmp_path / "config.toml"
        config_file.write_text(_make_toml(), encoding="utf-8")
        manager = ConfigManager(config_path=config_file)
        config = manager.load()
        assert config.gitlab_url == "https://gitlab.com"
        assert config.token == "glpat-validtoken"

    def test_URLの末尾スラッシュが除去される(self, tmp_path):
        config_file = tmp_path / "config.toml"
        config_file.write_text(_make_toml(url="https://gitlab.com/"), encoding="utf-8")
        manager = ConfigManager(config_path=config_file)
        config = manager.load()
        assert config.gitlab_url == "https://gitlab.com"

    def test_ファイルが存在しない場合にウィザードが起動する(self, tmp_path):
        config_file = tmp_path / "config.toml"
        manager = ConfigManager(config_path=config_file)
        with patch.object(manager, "_run_setup_wizard") as mock_wizard:
            mock_wizard.return_value = AppConfig(gitlab_url="https://gitlab.com", token="glpat-x")
            result = manager.load()
        mock_wizard.assert_called_once()
        assert result.gitlab_url == "https://gitlab.com"

    def test_TOMLパースエラー時にYを入力するとウィザードが起動する(self, tmp_path, monkeypatch):
        config_file = tmp_path / "config.toml"
        config_file.write_text("NOT VALID TOML ][[[", encoding="utf-8")
        manager = ConfigManager(config_path=config_file)

        monkeypatch.setattr("builtins.input", lambda _: "y")
        with patch.object(manager, "_run_setup_wizard") as mock_wizard:
            mock_wizard.return_value = AppConfig(gitlab_url="https://gitlab.com", token="glpat-x")
            manager.load()
        mock_wizard.assert_called_once()

    def test_TOMLパースエラー時にNを入力すると終了する(self, tmp_path, monkeypatch):
        config_file = tmp_path / "config.toml"
        config_file.write_text("NOT VALID TOML ][[[", encoding="utf-8")
        manager = ConfigManager(config_path=config_file)

        monkeypatch.setattr("builtins.input", lambda _: "n")
        with pytest.raises(SystemExit):
            manager.load()


class TestConfigManagerValidation:
    def _manager(self) -> ConfigManager:
        return ConfigManager(config_path=Path("/dev/null"))

    def test_有効な設定ではエラーが発生しない(self):
        cfg = AppConfig(gitlab_url="https://gitlab.com", token="glpat-abc")
        errors = ConfigManager._validate_gitlab_url(cfg.gitlab_url)
        assert errors == []

    def test_URLが空の場合はエラーになる(self):
        errors = ConfigManager._validate_gitlab_url("")
        assert len(errors) == 1
        assert "必須" in errors[0]

    def test_スキームなしのURLはエラーになる(self):
        errors = ConfigManager._validate_gitlab_url("gitlab.com")
        assert len(errors) == 1
        assert "http" in errors[0]

    def test_HTTPのURLは有効である(self):
        errors = ConfigManager._validate_gitlab_url("http://gitlab.example.com")
        assert errors == []

    def test_トークンが空の場合はエラーになる(self):
        errors = ConfigManager._validate_token("")
        assert len(errors) == 1
        assert "必須" in errors[0]

    def test_プレースホルダーのトークンはエラーになる(self):
        for placeholder in ["your-token-here", "xxx", "changeme"]:
            errors = ConfigManager._validate_token(placeholder)
            assert len(errors) == 1, f"Expected error for {placeholder!r}"
            assert "プレースホルダー" in errors[0]

    def test_有効なトークンはエラーにならない(self):
        errors = ConfigManager._validate_token("glpat-validtoken123")
        assert errors == []

    def test_無効なログレベルはエラーになる(self):
        errors = ConfigManager._validate_log_level("VERBOSE")
        assert len(errors) == 1
        assert "VERBOSE" in errors[0]

    def test_有効なログレベルはエラーにならない(self):
        for level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            assert ConfigManager._validate_log_level(level) == []

    def test_ログレベルの大小文字を区別しない(self):
        assert ConfigManager._validate_log_level("debug") == []

    def test_無効なテーマはエラーになる(self):
        errors = ConfigManager._validate_theme("myamazingtheme")
        assert len(errors) == 1
        assert "myamazingtheme" in errors[0]

    def test_有効なテーマはエラーにならない(self):
        assert ConfigManager._validate_theme("dark") == []
        assert ConfigManager._validate_theme("light") == []


class TestConfigManagerDefaultGeneration:
    def test_デフォルト設定が有効なTOMLである(self):
        manager = ConfigManager(config_path=Path("/dev/null"))
        content = manager.generate_default("https://gitlab.com", "glpat-xyz", "vi")
        parsed = tomllib.loads(content)
        assert parsed["gitlab"]["url"] == "https://gitlab.com"
        assert parsed["auth"]["token"] == "glpat-xyz"
        assert parsed["editor"]["command"] == "vi"


class TestConfigManagerPathResolution:
    def test_デフォルトパスがホームディレクトリを使用する(self, monkeypatch):
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        manager = ConfigManager()
        assert "glreview" in str(manager.config_path)
        assert str(manager.config_path).endswith("config.toml")

    def test_XDG_CONFIG_HOMEが尊重される(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        manager = ConfigManager()
        assert str(manager.config_path).startswith(str(tmp_path))

    def test_明示的なパスが使用される(self, tmp_path):
        custom = tmp_path / "my_config.toml"
        manager = ConfigManager(config_path=custom)
        assert manager.config_path == custom


class TestConfigManagerMapToConfig:
    def test_無効な設定でConfigErrorが発生する(self, tmp_path):
        config_file = tmp_path / "config.toml"
        config_file.write_text(
            _make_toml(url="not-a-url", token="your-token-here"),
            encoding="utf-8",
        )
        manager = ConfigManager(config_path=config_file)
        with pytest.raises(ConfigError):
            manager.load()

    def test_非glpatトークンで警告が表示される(self, tmp_path, capsys):
        config_file = tmp_path / "config.toml"
        config_file.write_text(_make_toml(token="oauth2-valid-token"), encoding="utf-8")
        manager = ConfigManager(config_path=config_file)
        manager.load()
        captured = capsys.readouterr()
        assert "glpat-" in captured.err

    def test_全設定項目がマッピングされる(self, tmp_path):
        content = (
            '[gitlab]\nurl = "https://gitlab.example.com"\nssl_verify = false\n'
            '[auth]\ntoken = "glpat-abc123"\n'
            '[editor]\ncommand = "nvim"\nterminal = "xterm -e"\n'
            '[logging]\nlevel = "DEBUG"\n'
            '[appearance]\ntheme = "light"\npygments_style = "monokai"\n'
            '[git]\nremote_name = "upstream"\n'
        )
        config_file = tmp_path / "config.toml"
        config_file.write_text(content, encoding="utf-8")
        manager = ConfigManager(config_path=config_file)
        config = manager.load()
        assert config.ssl_verify is False
        assert config.editor == "nvim"
        assert config.terminal == "xterm -e"
        assert config.log_level == "DEBUG"
        assert config.theme == "light"
        assert config.pygments_style == "monokai"
        assert config.remote_name == "upstream"


class TestConfigManagerValidateFull:
    def test_全バリデーションが実行される(self):
        manager = ConfigManager(config_path=Path("/tmp/dummy.toml"))  # noqa: S108
        config = AppConfig(gitlab_url="", token="", log_level="BAD", theme="bad_theme")
        errors = manager.validate(config)
        assert len(errors) >= 3

    def test_有効な設定ではエラーなし(self):
        manager = ConfigManager(config_path=Path("/tmp/dummy.toml"))  # noqa: S108
        config = AppConfig(gitlab_url="https://gitlab.com", token="glpat-abc")
        errors = manager.validate(config)
        assert errors == []


class TestSaveSetting:
    def test_既存キーを上書きする(self, tmp_path):
        content = '[appearance]\ntheme = "dark"\n'
        config_file = tmp_path / "config.toml"
        config_file.write_text(content, encoding="utf-8")
        manager = ConfigManager(config_path=config_file)
        manager.save_setting("appearance", "theme", "light")
        result = config_file.read_text(encoding="utf-8")
        assert 'theme = "light"' in result
        assert 'theme = "dark"' not in result

    def test_存在しないキーを追加する(self, tmp_path):
        content = '[appearance]\ntheme = "dark"\n'
        config_file = tmp_path / "config.toml"
        config_file.write_text(content, encoding="utf-8")
        manager = ConfigManager(config_path=config_file)
        manager.save_setting("appearance", "pygments_style", "monokai")
        result = config_file.read_text(encoding="utf-8")
        assert 'pygments_style = "monokai"' in result

    def test_ファイルが存在しない場合は何もしない(self, tmp_path):
        config_file = tmp_path / "nonexistent.toml"
        manager = ConfigManager(config_path=config_file)
        manager.save_setting("appearance", "theme", "dark")
        assert not config_file.exists()

    def test_複数セクションがある場合に正しいセクションを更新する(self, tmp_path):
        content = '[gitlab]\nurl = "https://gitlab.com"\n[appearance]\ntheme = "dark"\n'
        config_file = tmp_path / "config.toml"
        config_file.write_text(content, encoding="utf-8")
        manager = ConfigManager(config_path=config_file)
        manager.save_setting("gitlab", "url", "https://new.example.com")
        result = config_file.read_text(encoding="utf-8")
        assert 'url = "https://new.example.com"' in result
        assert 'theme = "dark"' in result
