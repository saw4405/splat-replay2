from __future__ import annotations

import threading
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np

from splat_replay.infrastructure.adapters.capture import video_file_capture
from splat_replay.infrastructure.adapters.capture.video_file_capture import (
    VideoFileCapture,
)


class _FakeVideoCapture:
    def __init__(self) -> None:
        self.read_started = threading.Event()
        self.allow_read_finish = threading.Event()
        self.read_in_progress = False
        self.released_during_read = False

    def isOpened(self) -> bool:
        return True

    def release(self) -> None:
        if self.read_in_progress:
            self.released_during_read = True

    def get(self, prop: int) -> float:
        if prop == video_file_capture.cv2.CAP_PROP_FPS:
            return 30.0
        return 0.0

    def read(self) -> tuple[bool, np.ndarray]:
        self.read_in_progress = True
        self.read_started.set()
        self.allow_read_finish.wait(timeout=2)
        self.read_in_progress = False
        return True, np.zeros((1, 1, 3), dtype=np.uint8)

    def grab(self) -> bool:
        return True


def test_setup_does_not_release_capture_during_read(monkeypatch) -> None:
    created_captures: list[_FakeVideoCapture] = []

    def _build_capture(_path: str) -> _FakeVideoCapture:
        capture = _FakeVideoCapture()
        created_captures.append(capture)
        return capture

    monkeypatch.setattr(
        video_file_capture, "resolve_video_input_path", lambda path: path
    )
    monkeypatch.setattr(video_file_capture.cv2, "VideoCapture", _build_capture)

    capture = VideoFileCapture(Path("dummy.mkv"), MagicMock())
    capture.setup()
    first_capture = created_captures[0]

    capture_thread = threading.Thread(target=capture.capture)
    capture_thread.start()
    assert first_capture.read_started.wait(timeout=1)

    setup_thread = threading.Thread(target=capture.setup)
    setup_thread.start()

    first_capture.allow_read_finish.set()
    capture_thread.join(timeout=2)
    setup_thread.join(timeout=2)

    assert not first_capture.released_during_read
