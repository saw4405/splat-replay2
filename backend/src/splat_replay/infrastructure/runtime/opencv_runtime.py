"""OpenCV のプロセス内 runtime 設定。"""

from __future__ import annotations

import platform

import cv2


def configure_opencv_thread_limit() -> None:
    """Windows の OpenCV worker 数を最大4に制限する。"""
    if platform.system() == "Windows" and cv2.getNumThreads() > 4:
        cv2.setNumThreads(4)
