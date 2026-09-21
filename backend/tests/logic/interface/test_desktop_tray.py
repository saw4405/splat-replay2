"""通知領域の生成・表示通知・破棄を実 Windows メッセージで確認する。"""

import sys
from pathlib import Path
from collections.abc import Callable
from typing import cast

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows 専用")


def test_tray_lifecycle_and_show_command() -> None:
    import win32con
    import win32gui
    from splat_replay.interface.gui.desktop_tray import DesktopTray

    if not win32gui.FindWindow("Shell_TrayWnd", None):
        pytest.skip(
            "対話デスクトップのタスクバーが必要。隔離環境では実行できない"
        )

    commands: list[str] = []
    tray = DesktopTray(
        Path(__file__).resolve().parents[3] / "assets/icon.ico",
        commands.append,
    )
    try:
        tray.start()
        for state in (
            "waiting",
            "recording",
            "processing",
            "attention",
            "starting",
        ):
            previous = tray.icon
            tray.set_status(state, "状態表示の確認")
            win32gui.SendMessage(tray.hwnd, win32con.WM_USER + 2, 0, 0)
            assert tray.applied_status == (state, "状態表示の確認")
            assert tray.icon != previous
        cast(
            Callable[[int, tuple[object, ...]], None],
            win32gui.Shell_NotifyIcon,
        )(win32gui.NIM_DELETE, (tray.hwnd, 0))
        win32gui.SendMessage(tray.hwnd, tray.taskbar_message, 0, 0)
        assert tray.applied_status == ("starting", "状態表示の確認")
        win32gui.SendMessage(
            tray.hwnd, win32con.WM_USER + 1, 0, win32con.WM_LBUTTONUP
        )
        assert commands == ["show"]
    finally:
        tray.close()
    assert not tray.thread.is_alive()
