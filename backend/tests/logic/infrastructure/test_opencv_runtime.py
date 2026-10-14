"""OpenCV runtime 設定のロジックテスト。"""

from __future__ import annotations

import pytest

from splat_replay.infrastructure.runtime import opencv_runtime


@pytest.mark.parametrize(
    ("system", "initial_threads", "expected_threads", "expected_calls"),
    [
        ("Windows", 1, 1, []),
        ("Windows", 4, 4, []),
        ("Windows", 8, 4, [4]),
        ("Darwin", 8, 8, []),
    ],
)
def test_configure_opencv_thread_limit(
    monkeypatch: pytest.MonkeyPatch,
    system: str,
    initial_threads: int,
    expected_threads: int,
    expected_calls: list[int],
) -> None:
    threads = initial_threads
    set_calls: list[int] = []

    def get_threads() -> int:
        return threads

    def set_threads(value: int) -> None:
        nonlocal threads
        set_calls.append(value)
        threads = value

    monkeypatch.setattr(opencv_runtime.platform, "system", lambda: system)
    monkeypatch.setattr(opencv_runtime.cv2, "getNumThreads", get_threads)
    monkeypatch.setattr(opencv_runtime.cv2, "setNumThreads", set_threads)

    opencv_runtime.configure_opencv_thread_limit()

    assert threads == expected_threads
    assert set_calls == expected_calls
