"""glreview.__main__ のユニットテスト。"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from glreview.__main__ import parse_args


class TestParseArgs:
    def test_defaults(self) -> None:
        with patch("sys.argv", ["glreview"]):
            args = parse_args()
        assert args.mr_id is None
        assert args.directory is None

    def test_with_mr_id(self) -> None:
        with patch("sys.argv", ["glreview", "42"]):
            args = parse_args()
        assert args.mr_id == 42

    def test_with_directory_short(self) -> None:
        with patch("sys.argv", ["glreview", "-C", "/some/path"]):
            args = parse_args()
        assert args.directory == Path("/some/path")

    def test_with_directory_long(self) -> None:
        with patch("sys.argv", ["glreview", "--directory", "/tmp/repo"]):  # noqa: S108
            args = parse_args()
        assert args.directory == Path("/tmp/repo")  # noqa: S108

    def test_with_mr_id_and_directory(self) -> None:
        with patch("sys.argv", ["glreview", "10", "-C", "/repo"]):
            args = parse_args()
        assert args.mr_id == 10
        assert args.directory == Path("/repo")


class TestMain:
    def test_main_calls_app_run(self) -> None:
        """main() が ConfigManager をロードして App を起動することを確認する。"""
        from glreview.__main__ import main

        mock_config = MagicMock()
        mock_config.log_level = "WARNING"
        mock_config_manager = MagicMock()
        mock_config_manager.load.return_value = mock_config

        mock_app = MagicMock()

        with (
            patch("sys.argv", ["glreview"]),
            patch("glreview.infrastructure.config.ConfigManager", return_value=mock_config_manager),
            patch("glreview.__main__.setup_logging"),
            patch("glreview.__main__.get_logger", return_value=MagicMock()),
            patch("glreview.tui.app.GLReviewApp", return_value=mock_app),
        ):
            main()

        mock_app.run.assert_called_once()

    def test_main_with_invalid_directory_exits(self, tmp_path) -> None:
        """存在しないディレクトリを指定するとsys.exit(1)が呼ばれることを確認する。"""
        from glreview.__main__ import main

        mock_config = MagicMock()
        mock_config.log_level = "WARNING"
        mock_config_manager = MagicMock()
        mock_config_manager.load.return_value = mock_config

        nonexistent = str(tmp_path / "nonexistent_dir")

        with (
            patch("sys.argv", ["glreview", "-C", nonexistent]),
            patch("glreview.infrastructure.config.ConfigManager", return_value=mock_config_manager),
            patch("glreview.__main__.setup_logging"),
            patch("glreview.__main__.get_logger", return_value=MagicMock()),
            pytest.raises(SystemExit) as exc_info,
        ):
            main()

        assert exc_info.value.code == 1

    def test_main_keyboard_interrupt_exits_zero(self) -> None:
        """KeyboardInterrupt が sys.exit(0) になることを確認する。"""
        from glreview.__main__ import main

        mock_config_manager = MagicMock()
        mock_config_manager.load.side_effect = KeyboardInterrupt

        with (
            patch("sys.argv", ["glreview"]),
            patch("glreview.infrastructure.config.ConfigManager", return_value=mock_config_manager),
            pytest.raises(SystemExit) as exc_info,
        ):
            main()

        assert exc_info.value.code == 0

    def test_main_exception_exits_one(self) -> None:
        """予期しない例外が sys.exit(1) になることを確認する。"""
        from glreview.__main__ import main

        mock_config_manager = MagicMock()
        mock_config_manager.load.side_effect = RuntimeError("something went wrong")

        with (
            patch("sys.argv", ["glreview"]),
            patch("glreview.infrastructure.config.ConfigManager", return_value=mock_config_manager),
            patch("glreview.__main__.get_logger", return_value=MagicMock()),
            pytest.raises(SystemExit) as exc_info,
        ):
            main()

        assert exc_info.value.code == 1

    def test_main_with_valid_directory(self, tmp_path) -> None:
        """存在するディレクトリを -C で渡すとアプリが起動することを確認する。"""
        from glreview.__main__ import main

        mock_config = MagicMock()
        mock_config.log_level = "WARNING"
        mock_config_manager = MagicMock()
        mock_config_manager.load.return_value = mock_config

        mock_app = MagicMock()

        with (
            patch("sys.argv", ["glreview", "-C", str(tmp_path)]),
            patch("glreview.infrastructure.config.ConfigManager", return_value=mock_config_manager),
            patch("glreview.__main__.setup_logging"),
            patch("glreview.__main__.get_logger", return_value=MagicMock()),
            patch("glreview.tui.app.GLReviewApp", return_value=mock_app),
        ):
            main()

        mock_app.run.assert_called_once()
