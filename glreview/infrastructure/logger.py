"""glreview のロギングインフラストラクチャ。"""

from __future__ import annotations

import logging
import logging.handlers
import os
import re
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

_LOG_DIR_NAME = "logs"
_LOG_FILE_PREFIX = "glreview_"
_MAX_BYTES = 5 * 1024 * 1024  # 5 MB
_BACKUP_COUNT = 3
_LOG_RETENTION_DAYS = 30

# SECURITY-03: glpat-トークンと長い英数字文字列をマスクする
_MASK_PATTERNS = [
    re.compile(r"glpat-[A-Za-z0-9_\-]+"),
    re.compile(r"[A-Za-z0-9]{20,}"),
]
_REDACTED = "***REDACTED***"


def _default_log_dir() -> Path:
    xdg = os.environ.get("XDG_CONFIG_HOME", "")
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / "glreview" / _LOG_DIR_NAME


class TokenMaskingFilter(logging.Filter):
    """ログレコードから機密トークンをマスクするフィルター(SECURITY-03)。"""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = _mask(str(record.msg))
        record.args = _mask_args(record.args)
        return True


def _mask(text: str) -> str:
    for pattern in _MASK_PATTERNS:
        text = pattern.sub(_REDACTED, text)
    return text


def _mask_args(
    args: tuple | dict | None,
) -> tuple | dict | None:
    if args is None:
        return None
    if isinstance(args, dict):
        return {k: _mask(str(v)) if isinstance(v, str) else v for k, v in args.items()}
    return tuple(
        {k: _mask(str(v)) if isinstance(v, str) else v for k, v in a.items()}
        if isinstance(a, dict)
        else _mask(str(a))
        if isinstance(a, str)
        else a
        for a in args
    )


def setup_logging(
    log_level: str = "INFO",
    log_dir: Path | None = None,
) -> None:
    """ローテーションファイルハンドラーでルートロガーを設定する。

    アプリケーション起動時に一度だけ呼び出すこと。
    """
    resolved_dir = log_dir or _default_log_dir()

    try:
        resolved_dir.mkdir(parents=True, exist_ok=True)
        if os.name != "nt":
            os.chmod(resolved_dir, 0o700)
    except OSError as exc:
        print(
            f"警告: ログディレクトリを作成できません ({exc}). ログなしで続行します。",
            file=sys.stderr,
        )
        _configure_null_handler()
        return

    today = datetime.now(tz=UTC).strftime("%Y-%m-%d")
    log_file = resolved_dir / f"{_LOG_FILE_PREFIX}{today}.log"

    try:
        handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=_MAX_BYTES,
            backupCount=_BACKUP_COUNT,
            encoding="utf-8",
        )
        if os.name != "nt":
            os.chmod(log_file, 0o600)
    except OSError as exc:
        print(
            f"警告: ログファイルを開けません ({exc}). ログなしで続行します。",
            file=sys.stderr,
        )
        _configure_null_handler()
        return

    formatter = logging.Formatter(
        fmt="{asctime} [{levelname}] {name}: {message}",
        datefmt="%Y-%m-%dT%H:%M:%S",
        style="{",
    )
    handler.setFormatter(formatter)
    handler.addFilter(TokenMaskingFilter())

    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    root = logging.getLogger()
    root.setLevel(numeric_level)
    # テスト実行時など、繰り返し呼ばれた場合の重複ハンドラーを避ける
    root.handlers.clear()
    root.addHandler(handler)

    _cleanup_old_logs(resolved_dir)


def _configure_null_handler() -> None:
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(logging.NullHandler())


def get_logger(name: str) -> logging.Logger:
    """'glreview' 名前空間の名前付きロガーを返す。"""
    if name.startswith("glreview"):
        return logging.getLogger(name)
    return logging.getLogger(f"glreview.{name}")


def _cleanup_old_logs(log_dir: Path) -> None:
    """`_LOG_RETENTION_DAYS`日より古いログファイルを削除する。"""
    cutoff = datetime.now(tz=UTC) - timedelta(days=_LOG_RETENTION_DAYS)
    pattern = f"{_LOG_FILE_PREFIX}*.log"
    try:
        for log_file in log_dir.glob(pattern):
            try:
                date_str = log_file.stem.removeprefix(_LOG_FILE_PREFIX)
                file_date = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=UTC)
                if file_date < cutoff:
                    log_file.unlink()
            except (ValueError, OSError):
                # 予期しないファイル名やパーミッションエラーは無視する
                pass
    except OSError:
        pass
