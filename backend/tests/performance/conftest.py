"""Performance tests の共通 runtime 初期化。"""

from __future__ import annotations

import pytest

from splat_replay.infrastructure.runtime.opencv_runtime import (
    configure_opencv_thread_limit,
)


@pytest.fixture(scope="session", autouse=True)
def configure_opencv_threads_for_performance() -> None:
    """測定開始前に本番と同じ OpenCV thread 上限を適用する。"""
    configure_opencv_thread_limit()
