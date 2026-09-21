"""Windows 通知領域の表示・終了メニュー。"""

from __future__ import annotations

import threading
import contextlib
from collections.abc import Callable
from pathlib import Path
from typing import SupportsInt, cast

import win32api
import win32con
import win32gui


# pywin32 の一部 stub は引数や書き込み可能なプロパティを欠くため、実際の API 型を境界で補う。
class DesktopTray:
    def __init__(
        self, icon_path: Path, command: Callable[[str], None]
    ) -> None:
        self.icon_path = icon_path
        self.command = command
        self.hwnd = 0
        self.icon = 0
        self.icons: dict[str, int] = {}
        self.status = ("starting", "起動中")
        self.applied_status: tuple[str, str] | None = None
        self.taskbar_message = win32gui.RegisterWindowMessage("TaskbarCreated")
        self.started = threading.Event()
        self.error: Exception | None = None
        self.thread = threading.Thread(
            target=self._run, name="desktop-tray", daemon=True
        )

    def start(self) -> None:
        self.thread.start()
        if not self.started.wait(10):
            raise RuntimeError("通知領域の起動が完了しませんでした")
        if self.error is not None:
            raise RuntimeError(
                "通知領域を起動できませんでした"
            ) from self.error

    def close(self) -> None:
        if self.hwnd:
            win32gui.PostMessage(self.hwnd, win32con.WM_CLOSE, 0, 0)
            self.thread.join(timeout=5)

    def set_status(self, state: str, description: str) -> None:
        status = (state, description)
        if status != self.status:
            self.status = status
            if self.hwnd:
                win32gui.PostMessage(self.hwnd, win32con.WM_USER + 2, 0, 0)

    def _window_proc(
        self, hwnd: int, message: int, wparam: int, lparam: int
    ) -> int:
        if message == win32con.WM_USER + 2:
            self._add_icon(win32gui.NIM_MODIFY)
            return 0
        if message == self.taskbar_message:
            try:
                self._add_icon()
            except Exception as exc:
                self.error = exc
                self.command("show")
            return 0
        if message == win32con.WM_USER + 1:
            if lparam == win32con.WM_LBUTTONUP:
                self.command("show")
            elif lparam == win32con.WM_RBUTTONUP:
                menu = win32gui.CreatePopupMenu()
                try:
                    for index, label in enumerate(
                        (
                            "画面を開く",
                            "更新予約を取り消す",
                            "完全終了（処理完了を待つ）",
                        ),
                        1,
                    ):
                        cast(
                            Callable[[int, int, int, str], None],
                            win32gui.AppendMenu,
                        )(menu, win32con.MF_STRING, index, label)
                    win32gui.SetForegroundWindow(hwnd)
                    x, y = win32gui.GetCursorPos()
                    selected = cast(
                        Callable[[int, int, int, int, int, int, object], int],
                        win32gui.TrackPopupMenu,
                    )(
                        menu,
                        win32con.TPM_RETURNCMD | win32con.TPM_RIGHTBUTTON,
                        x,
                        y,
                        0,
                        hwnd,
                        (0, 0, 0, 0),
                    )
                    if selected:
                        self.command(
                            {1: "show", 2: "cancel", 3: "quit"}[selected]
                        )
                    win32gui.PostMessage(hwnd, win32con.WM_NULL, 0, 0)
                finally:
                    cast(Callable[[int], None], win32gui.DestroyMenu)(menu)
            return 0
        if message == win32con.WM_CLOSE:
            win32gui.DestroyWindow(hwnd)
            return 0
        if message == win32con.WM_DESTROY:
            win32gui.PostQuitMessage(0)
            return 0
        return win32gui.DefWindowProc(hwnd, message, wparam, lparam)

    def _run(self) -> None:
        icon = 0
        atom = 0
        added = False
        try:
            window_class = win32gui.WNDCLASS()
            setattr(window_class, "hInstance", win32api.GetModuleHandle(None))
            setattr(window_class, "lpszClassName", "SplatReplayTray")
            setattr(window_class, "lpfnWndProc", self._window_proc)
            atom = win32gui.RegisterClass(window_class)
            self.hwnd = win32gui.CreateWindow(
                atom,
                "SplatReplay",
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                window_class.hInstance,
                None,
            )
            for state in (
                "starting",
                "waiting",
                "recording",
                "processing",
                "attention",
            ):
                icon = win32gui.LoadImage(
                    0,
                    str(self.icon_path.parent / "tray" / f"{state}.ico"),
                    win32con.IMAGE_ICON,
                    0,
                    0,
                    win32con.LR_LOADFROMFILE | win32con.LR_DEFAULTSIZE,
                )
                self.icons[state] = int(cast(SupportsInt, icon))
            self._add_icon()
            added = True
            self.started.set()
            win32gui.PumpMessages()
        except Exception as exc:
            self.error = exc
            self.started.set()
        finally:
            if added:
                # Explorer が終了した場合はアイコンも既に消滅している。
                with contextlib.suppress(Exception):
                    cast(
                        Callable[[int, tuple[object, ...]], None],
                        win32gui.Shell_NotifyIcon,
                    )(win32gui.NIM_DELETE, (self.hwnd, 0))
            if self.hwnd and win32gui.IsWindow(self.hwnd):
                win32gui.DestroyWindow(self.hwnd)
            for handle in self.icons.values():
                win32gui.DestroyIcon(handle)
            self.icons.clear()
            if atom:
                win32gui.UnregisterClass(atom, win32api.GetModuleHandle(None))
            self.hwnd = 0

    def _add_icon(self, operation: int = win32gui.NIM_ADD) -> None:
        status = self.status
        self.icon = self.icons[status[0]]
        cast(
            Callable[[int, tuple[object, ...]], None],
            win32gui.Shell_NotifyIcon,
        )(
            operation,
            (
                self.hwnd,
                0,
                win32gui.NIF_ICON | win32gui.NIF_MESSAGE | win32gui.NIF_TIP,
                win32con.WM_USER + 1,
                self.icon,
                ("SplatReplay — " + status[1])[:127],
            ),
        )
        self.applied_status = status
