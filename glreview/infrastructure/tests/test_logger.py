"""glreview.infrastructure.logger のユニットテスト。"""

from __future__ import annotations

import logging
import logging.handlers
from datetime import UTC, datetime, timedelta
from pathlib import Path

from glreview.infrastructure.logger import (
    TokenMaskingFilter,
    _cleanup_old_logs,
    _mask,
    get_logger,
    setup_logging,
)


class TestTokenMaskingFilter:
    def _make_record(self, msg: str, args=None) -> logging.LogRecord:
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg=msg,
            args=args or (),
            exc_info=None,
        )
        return record

    def test_glpatトークンがマスクされる(self):
        f = TokenMaskingFilter()
        record = self._make_record("token=glpat-abcdefghij1234567890")
        f.filter(record)
        assert "glpat-" not in record.msg
        assert "***REDACTED***" in record.msg

    def test_長い英数字文字列がマスクされる(self):
        f = TokenMaskingFilter()
        record = self._make_record("key=abcdefghijklmnopqrstu")  # 21文字
        f.filter(record)
        assert "***REDACTED***" in record.msg

    def test_短い文字列はマスクされない(self):
        f = TokenMaskingFilter()
        record = self._make_record("abc123")  # 6文字 — 短すぎる
        f.filter(record)
        assert record.msg == "abc123"

    def test_タプル引数内のトークンがマスクされる(self):
        f = TokenMaskingFilter()
        record = self._make_record("value: %s", args=("glpat-secret123456789",))
        f.filter(record)
        assert all("glpat-" not in str(a) for a in record.args)

    def test_辞書引数内のトークンがマスクされる(self):
        f = TokenMaskingFilter()
        record = self._make_record("value: %(key)s", args=({"key": "glpat-secret12345678901"},))
        f.filter(record)
        assert "glpat-" not in str(record.args)

    def test_Noneの引数はNoneのまま(self):
        f = TokenMaskingFilter()
        record = self._make_record("no args")
        record.args = None
        f.filter(record)
        assert record.args is None

    def test_フィルターがTrueを返す(self):
        f = TokenMaskingFilter()
        record = self._make_record("hello")
        assert f.filter(record) is True


class TestMaskFunction:
    def test_glpatトークン単体がマスクされる(self):
        result = _mask("glpat-ABCDEFGHIJ1234567890")
        assert result == "***REDACTED***"

    def test_文章中のglpatトークンがマスクされる(self):
        result = _mask("Using token glpat-abc123def456ghi789 for auth")
        assert "glpat-" not in result

    def test_長い英数字文字列がマスクされる(self):
        result = _mask("hash=aAbBcCdDeEfFgGhHiIjJ")
        assert "***REDACTED***" in result

    def test_19文字の文字列はマスクされない(self):
        result = _mask("abcdefghijklmnopqrs")  # 19文字
        assert result == "abcdefghijklmnopqrs"

    def test_20文字の文字列はマスクされる(self):
        result = _mask("abcdefghijklmnopqrst")  # 20文字
        assert "***REDACTED***" in result


class TestSetupLogging:
    def test_RotatingFileHandlerが作成される(self, tmp_path):
        setup_logging("DEBUG", log_dir=tmp_path)
        root = logging.getLogger()
        assert any(isinstance(h, logging.handlers.RotatingFileHandler) for h in root.handlers)

    def test_ログファイルが作成される(self, tmp_path):
        setup_logging("INFO", log_dir=tmp_path)
        log_files = list(tmp_path.glob("glreview_*.log"))
        assert len(log_files) >= 1

    def test_ログレベルが設定される(self, tmp_path):
        setup_logging("DEBUG", log_dir=tmp_path)
        assert logging.getLogger().level == logging.DEBUG

    def test_TokenMaskingFilterが付与される(self, tmp_path):
        setup_logging("INFO", log_dir=tmp_path)
        root = logging.getLogger()
        for handler in root.handlers:
            if isinstance(handler, logging.handlers.RotatingFileHandler):
                filter_types = [type(f) for f in handler.filters]
                assert TokenMaskingFilter in filter_types

    def test_ディレクトリ作成失敗時にNullHandlerにフォールバックする(self, tmp_path, monkeypatch):
        bad_dir = tmp_path / "no_perm"

        original_mkdir = Path.mkdir

        def fail_mkdir(self, *args, **kwargs):
            if self == bad_dir:
                raise OSError("permission denied")
            original_mkdir(self, *args, **kwargs)

        monkeypatch.setattr(Path, "mkdir", fail_mkdir)
        setup_logging("INFO", log_dir=bad_dir)
        root = logging.getLogger()
        assert any(isinstance(h, logging.NullHandler) for h in root.handlers)


class TestGetLogger:
    def test_名前空間付きロガーを返す(self):
        logger = get_logger("mymodule")
        assert logger.name == "glreview.mymodule"

    def test_既に名前空間が付いている場合は二重にならない(self):
        logger = get_logger("glreview.something")
        assert logger.name == "glreview.something"

    def test_logging_Loggerのインスタンスを返す(self):
        assert isinstance(get_logger("test"), logging.Logger)


class TestCleanupOldLogs:
    def test_古いログファイルが削除される(self, tmp_path):
        old_date = (datetime.now(tz=UTC) - timedelta(days=31)).strftime("%Y-%m-%d")
        old_file = tmp_path / f"glreview_{old_date}.log"
        old_file.write_text("old log", encoding="utf-8")

        _cleanup_old_logs(tmp_path)
        assert not old_file.exists()

    def test_最近のログファイルは保持される(self, tmp_path):
        recent_date = datetime.now(tz=UTC).strftime("%Y-%m-%d")
        recent_file = tmp_path / f"glreview_{recent_date}.log"
        recent_file.write_text("recent log", encoding="utf-8")

        _cleanup_old_logs(tmp_path)
        assert recent_file.exists()

    def test_予期しないファイル名は無視される(self, tmp_path):
        weird = tmp_path / "glreview_notadate.log"
        weird.write_text("weird", encoding="utf-8")
        # 例外が発生しないことを確認
        _cleanup_old_logs(tmp_path)
        assert weird.exists()
