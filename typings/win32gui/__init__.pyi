from __future__ import annotations

from typing import Callable, Optional

HWND = int

def IsWindowVisible(handle: HWND) -> bool: ...
def GetWindowText(handle: HWND) -> str: ...
def EnumWindows(
    callback: Callable[[HWND, Optional[int]], bool], param: Optional[int]
) -> None: ...
