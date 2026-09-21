"""同一ユーザーセッション・配置先のインスタンスを Windows オブジェクトで制御する。"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pywintypes
import win32api
import win32event
import winerror
import win32security
import win32con


COMMANDS = ("show", "update", "cancel", "quit", "resume")
STATES = ("ready", "waiting", "held", "cancelled")


class DesktopInstance:
    def __init__(self, executable: Path, *, client_only: bool = False) -> None:
        token = win32security.OpenProcessToken(
            win32api.GetCurrentProcess(), win32con.TOKEN_QUERY
        )
        try:
            user = win32security.GetTokenInformation(
                token, win32security.TokenUser
            )[0]
        finally:
            win32api.CloseHandle(token)
        identity = str(
            executable.resolve()
        ).casefold() + win32security.ConvertSidToStringSid(user)
        key = hashlib.sha256(identity.encode()).hexdigest()[:24]
        self.prefix = rf"Local\SplatReplay-{key}"
        security = pywintypes.SECURITY_ATTRIBUTES()
        acl = win32security.ACL()
        acl.AddAccessAllowedAce(win32security.ACL_REVISION, 0x001F0003, user)
        security.SECURITY_DESCRIPTOR.SetSecurityDescriptorDacl(
            True, acl, False
        )
        self.handles: dict[str, int] = {}
        self.mutex: int | None = None
        self.owner = False
        if client_only:
            try:
                self.mutex = win32event.OpenMutex(
                    0x00100000, False, self.prefix + "-owner"
                )
            except pywintypes.error:
                pass
            return
        self.mutex = win32event.CreateMutex(
            security, False, self.prefix + "-owner"
        )
        self.owner = win32api.GetLastError() != winerror.ERROR_ALREADY_EXISTS
        if self.owner:
            for name in (*COMMANDS, *STATES):
                self.handles[name] = win32event.CreateEvent(
                    security, name in STATES, False, self.prefix + "-" + name
                )

    def send(self, command: str) -> bool:
        if command not in COMMANDS:
            raise ValueError("未定義のデスクトップ操作です")
        try:
            handle = win32event.OpenEvent(
                win32event.EVENT_MODIFY_STATE,
                False,
                self.prefix + "-" + command,
            )
        except pywintypes.error:
            return False
        try:
            win32event.SetEvent(handle)
            return True
        finally:
            win32api.CloseHandle(handle)

    def take(self, command: str) -> bool:
        return (
            win32event.WaitForSingleObject(self.handles[command], 0)
            == win32event.WAIT_OBJECT_0
        )

    def updating(self) -> bool:
        """差し替え中の新規起動を止める（保留起動だけは更新側から許可する）。"""
        try:
            handle = win32event.OpenMutex(
                0x00100000, False, self.prefix + "-updater"
            )
        except pywintypes.error:
            return False
        win32api.CloseHandle(handle)
        return True

    def state(self, name: str, value: bool) -> None:
        if value:
            win32event.SetEvent(self.handles[name])
        else:
            win32event.ResetEvent(self.handles[name])

    def status(self) -> int:
        """0=稼働、3=起動中、4=不在、5=更新待ち、6=保留起動。"""
        if self.owner or self.mutex is None:
            return 4
        for name, code in (
            ("waiting", 5),
            ("held", 6),
            ("cancelled", 7),
            ("ready", 0),
        ):
            try:
                handle = win32event.OpenEvent(
                    0x00100000, False, self.prefix + "-" + name
                )
            except pywintypes.error:
                continue
            try:
                if (
                    win32event.WaitForSingleObject(handle, 0)
                    == win32event.WAIT_OBJECT_0
                ):
                    return code
            finally:
                win32api.CloseHandle(handle)
        return 3

    def close(self) -> None:
        for handle in self.handles.values():
            win32api.CloseHandle(handle)
        self.handles.clear()
        if self.mutex is not None:
            win32api.CloseHandle(self.mutex)
            self.mutex = None
