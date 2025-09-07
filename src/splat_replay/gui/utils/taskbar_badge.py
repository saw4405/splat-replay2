# taskbar_badge.py
import ctypes
from ctypes import wintypes
from pathlib import Path
from typing import Optional

import comtypes
from comtypes import COMMETHOD, GUID, HRESULT


# --- ITaskbarList / ITaskbarList2 / ITaskbarList3 定義（必要部分のみ） ---
class ITaskbarList(comtypes.IUnknown):
    _iid_ = GUID("{56FDF342-FD6D-11d0-958A-006097C9A090}")
    _methods_ = [
        COMMETHOD([], HRESULT, "HrInit"),
        COMMETHOD([], HRESULT, "AddTab", (["in"], wintypes.HWND, "hwnd")),
        COMMETHOD([], HRESULT, "DeleteTab", (["in"], wintypes.HWND, "hwnd")),
        COMMETHOD([], HRESULT, "ActivateTab", (["in"], wintypes.HWND, "hwnd")),
        COMMETHOD(
            [], HRESULT, "SetActiveAlt", (["in"], wintypes.HWND, "hwnd")
        ),
    ]


class ITaskbarList2(ITaskbarList):
    _iid_ = GUID("{602D4995-B13A-429b-A66E-1935E44F4317}")
    _methods_ = [
        COMMETHOD(
            [],
            HRESULT,
            "MarkFullscreenWindow",
            (["in"], wintypes.HWND, "hwnd"),
            (["in"], wintypes.BOOL, "fFullscreen"),
        ),
    ]


class ITaskbarList3(ITaskbarList2):
    _iid_ = GUID("{C43DC798-95D1-4BEA-9030-BB99E2983A1A}")
    _methods_ = [
        COMMETHOD(
            [],
            HRESULT,
            "SetProgressValue",
            (["in"], wintypes.HWND, "hwnd"),
            (["in"], ctypes.c_ulonglong, "ullCompleted"),
            (["in"], ctypes.c_ulonglong, "ullTotal"),
        ),
        COMMETHOD(
            [],
            HRESULT,
            "SetProgressState",
            (["in"], wintypes.HWND, "hwnd"),
            (["in"], ctypes.c_int, "tbpFlags"),
        ),
        COMMETHOD(
            [],
            HRESULT,
            "RegisterTab",
            (["in"], wintypes.HWND, "hwndTab"),
            (["in"], wintypes.HWND, "hwndMDI"),
        ),
        COMMETHOD(
            [], HRESULT, "UnregisterTab", (["in"], wintypes.HWND, "hwndTab")
        ),
        COMMETHOD(
            [],
            HRESULT,
            "SetTabOrder",
            (["in"], wintypes.HWND, "hwndTab"),
            (["in"], wintypes.HWND, "hwndInsertBefore"),
        ),
        COMMETHOD(
            [],
            HRESULT,
            "SetTabActive",
            (["in"], wintypes.HWND, "hwndTab"),
            (["in"], wintypes.HWND, "hwndMDI"),
            (["in"], ctypes.c_uint, "dwReserved"),
        ),
        COMMETHOD(
            [],
            HRESULT,
            "ThumbBarAddButtons",
            (["in"], wintypes.HWND, "hwnd"),
            (["in"], ctypes.c_uint, "cButtons"),
            (["in"], ctypes.c_void_p, "pButtons"),
        ),
        COMMETHOD(
            [],
            HRESULT,
            "ThumbBarUpdateButtons",
            (["in"], wintypes.HWND, "hwnd"),
            (["in"], ctypes.c_uint, "cButtons"),
            (["in"], ctypes.c_void_p, "pButtons"),
        ),
        COMMETHOD(
            [],
            HRESULT,
            "ThumbBarSetImageList",
            (["in"], wintypes.HWND, "hwnd"),
            (["in"], wintypes.HANDLE, "himl"),
        ),
        # ★ 目的の API
        COMMETHOD(
            [],
            HRESULT,
            "SetOverlayIcon",
            (["in"], wintypes.HWND, "hwnd"),
            (["in"], wintypes.HICON, "hIcon"),
            (["in"], ctypes.c_wchar_p, "pszDescription"),
        ),
        COMMETHOD(
            [],
            HRESULT,
            "SetThumbnailTooltip",
            (["in"], wintypes.HWND, "hwnd"),
            (["in"], ctypes.c_wchar_p, "pszTip"),
        ),
        COMMETHOD(
            [],
            HRESULT,
            "SetThumbnailClip",
            (["in"], wintypes.HWND, "hwnd"),
            (["in"], ctypes.POINTER(wintypes.RECT), "prcClip"),
        ),
    ]


CLSID_TaskbarList = GUID("{56FDF344-FD6D-11d0-958A-006097C9A090}")

# Win32 icon loading flags
LR_DEFAULTSIZE = 0x00000040
LR_LOADFROMFILE = 0x00000010
IMAGE_ICON = 1

_user32 = ctypes.windll.user32


class TaskbarBadge:
    """
    Windows タスクバーの「バッジ」（オーバーレイアイコン）を管理するクラス。
    - set_overlay_icon(ico_path):  .ico を重ねる
    - clear():                     解除
    - close():                     COM 解放（明示的に呼ぶか、コンテキストマネージャを利用）
    """

    def __init__(self, hwnd: int):
        """
        Parameters
        ----------
        hwnd : int
            Tk/Toplevel の winfo_id() で取得した HWND
        """
        if not hwnd:
            raise ValueError("hwnd is invalid (0).")
        self.hwnd = wintypes.HWND(hwnd)
        self._taskbar: Optional[ITaskbarList3] = None
        self._com_initialized = False
        self._ensure_com()

    # --- public API ---
    def set_overlay_icon(
        self, ico_path: Path, description: str = "badge"
    ) -> None:
        """指定した .ico をオーバーレイとして重ねる。"""
        ico_path = Path(ico_path)
        if not ico_path.exists():
            raise FileNotFoundError(ico_path)

        taskbar = self._get_taskbar()
        hicon = self._load_hicon_from_ico(ico_path)
        if not hicon:
            raise OSError(f"LoadImageW failed: {ico_path}")
        hr = taskbar.SetOverlayIcon(self.hwnd, hicon, description)
        if hr != 0:
            raise OSError(f"SetOverlayIcon failed: 0x{hr:08X}")

    def clear(self) -> None:
        """オーバーレイを解除。"""
        taskbar = self._get_taskbar()
        hr = taskbar.SetOverlayIcon(self.hwnd, None, None)
        if hr != 0:
            raise OSError(f"Clear(SetOverlayIcon None) failed: 0x{hr:08X}")

    def close(self) -> None:
        """COM を解放。アプリ終了時などに呼ぶ。"""
        # comtypes は参照カウントに任せてもよいが、明示的に Uninitialize しておく
        if self._taskbar is not None:
            self._taskbar = None
        if self._com_initialized:
            comtypes.CoUninitialize()
            self._com_initialized = False

    # --- context manager support ---
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()

    # --- internals ---
    def _ensure_com(self) -> None:
        # 既に初期化済みなら何もしない
        if self._com_initialized:
            return
        comtypes.CoInitialize()  # 同じスレッドで複数回呼んでも OK
        self._com_initialized = True

    def _get_taskbar(self) -> ITaskbarList3:
        if self._taskbar is not None:
            return self._taskbar
        self._ensure_com()
        obj = comtypes.CoCreateInstance(
            CLSID_TaskbarList, interface=ITaskbarList3
        )
        hr = obj.HrInit()
        if hr != 0:
            raise OSError(f"HrInit failed: 0x{hr:08X}")
        self._taskbar = obj
        return self._taskbar

    @staticmethod
    def _load_hicon_from_ico(ico_path: Path) -> wintypes.HICON:
        return _user32.LoadImageW(
            None,
            str(ico_path),
            IMAGE_ICON,
            0,
            0,
            LR_LOADFROMFILE | LR_DEFAULTSIZE,
        )
