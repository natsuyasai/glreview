"""glreview アプリケーションのエントリーポイント。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from glreview.infrastructure.logger import get_logger, setup_logging


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="glreview",
        description="A TUI application for browsing and commenting on GitLab merge requests",
    )
    parser.add_argument(
        "mr_id",
        nargs="?",
        type=int,
        default=None,
        help="Merge request IID to open directly on startup",
    )
    parser.add_argument(
        "-C",
        "--directory",
        type=Path,
        default=None,
        metavar="DIR",
        help="Run as if started in DIR instead of the current working directory",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    try:
        from glreview.infrastructure.config import ConfigManager

        config_manager = ConfigManager()
        config = config_manager.load()

        setup_logging(config.log_level)
        logger = get_logger(__name__)
        logger.info("glreview starting")

        cwd: Path | None = None
        if args.directory is not None:
            cwd = args.directory.resolve()
            if not cwd.is_dir():
                print(f"Error: '{cwd}' is not a directory", file=sys.stderr)
                sys.exit(1)
            logger.info("Working directory: %s", cwd)

        from glreview.tui.app import GLReviewApp

        app = GLReviewApp(
            config=config, config_manager=config_manager, initial_mr_id=args.mr_id, cwd=cwd
        )
        app.run()

    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        sys.exit(0)
    except Exception as exc:
        logger_fallback = get_logger(__name__)
        logger_fallback.exception("Unhandled exception during startup")
        # SECURITY-09: ユーザーには汎用的なメッセージのみ表示する
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
