"""Webview desktop application entrypoint."""

from __future__ import annotations

import multiprocessing
import sys
import traceback

from splat_replay.infrastructure.filesystem import PROJECT_ROOT
from splat_replay.infrastructure.logging import get_logger
from splat_replay.interface.gui.webview_app import SplatReplayWebViewApp


def main() -> None:
    """Entry point for the WebView desktop app."""
    logger = get_logger()

    try:
        logger.info("=== Splat Replay WebView App Starting ===")
        logger.info(f"Python executable: {sys.executable}")
        logger.info(f"Frozen: {getattr(sys, 'frozen', False)}")
        logger.info(f"PROJECT_ROOT: {PROJECT_ROOT}")

        # Windows multiprocessing support
        if sys.platform == "win32":
            multiprocessing.freeze_support()

        app_instance = SplatReplayWebViewApp(
            project_root=PROJECT_ROOT,
            logger=logger,
            backend_app_module="splat_replay.bootstrap.web_app:app",
        )
        app_instance.run()

    except Exception as e:
        logger.error("Fatal error occurred", error=str(e), exc_info=True)
        print(f"\n{'=' * 60}")
        print("FATAL ERROR:")
        print(f"{'=' * 60}")
        print(f"{type(e).__name__}: {e}")
        print(f"\n{'=' * 60}")
        print("Traceback:")
        print(f"{'=' * 60}")
        traceback.print_exc()
        print(f"{'=' * 60}\n")
        raise


__all__ = ["main"]


if __name__ == "__main__":
    main()
