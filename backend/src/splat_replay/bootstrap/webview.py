"""Webview desktop application entrypoint."""

from __future__ import annotations

import multiprocessing
import os
import sys
import traceback
import argparse
from pathlib import Path

# PyInstaller の windowed モードでは標準出力が存在しない。
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")  # noqa: SIM115
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")  # noqa: SIM115

# frozen worker が GUI などの重い import を実行する前に分岐させる。
if __name__ == "__main__" and sys.platform == "win32":
    multiprocessing.freeze_support()

from splat_replay.infrastructure.config import load_settings_from_toml
from splat_replay.infrastructure.filesystem import PROJECT_ROOT, RUNTIME_ROOT
from splat_replay.infrastructure.logging import get_logger
from splat_replay.interface.gui.webview_app import (
    SplatReplayWebViewApp,
    resolve_backend_hosts,
)


def main() -> None:
    """Entry point for the WebView desktop app."""
    logger = get_logger()
    parser = argparse.ArgumentParser(description="SplatReplay デスクトップ")
    parser.add_argument("--background", action="store_true")
    parser.add_argument("--hold", action="store_true")
    parser.add_argument(
        "--desktop-command",
        choices=("show", "update", "cancel", "quit", "resume", "status"),
    )
    args = parser.parse_args()
    instance = None
    if sys.platform == "win32":
        from splat_replay.infrastructure.adapters.system.desktop_instance import (
            DesktopInstance,
        )

        identity = (
            Path(sys.executable)
            if getattr(sys, "frozen", False)
            else PROJECT_ROOT / "SplatReplay.exe"
        )
        instance = DesktopInstance(
            identity, client_only=args.desktop_command is not None
        )
        if args.desktop_command is not None or not instance.owner:
            try:
                if args.desktop_command == "status":
                    code = instance.status()
                elif instance.owner:
                    code = 4
                else:
                    code = (
                        0
                        if instance.send(args.desktop_command or "show")
                        else 3
                    )
            finally:
                instance.close()
            raise SystemExit(code)
        if instance.updating() and not args.hold:
            instance.close()
            logger.info(
                "アプリを更新しています。完了後にもう一度開いてください"
            )
            raise SystemExit(8)

    try:
        logger.info("=== Splat Replay WebView App Starting ===")
        logger.info(f"Python executable: {sys.executable}")
        logger.info(f"Frozen: {getattr(sys, 'frozen', False)}")
        logger.info(f"PROJECT_ROOT: {PROJECT_ROOT}")

        settings = load_settings_from_toml()
        backend_bind_host, backend_url_host = resolve_backend_hosts(
            settings.remote_access.enabled
        )
        app_instance = SplatReplayWebViewApp(
            project_root=PROJECT_ROOT,
            startup_video=RUNTIME_ROOT / "assets" / "startup-loading.mp4",
            logger=logger,
            backend_app_module="splat_replay.bootstrap.web_app:app",
            render_mode=settings.webview.render_mode,
            backend_bind_host=backend_bind_host,
            backend_url_host=backend_url_host,
            desktop_control=instance,
            background=args.background,
            hold=args.hold,
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
    finally:
        if instance is not None:
            instance.close()


__all__ = ["main"]


if __name__ == "__main__":
    main()
