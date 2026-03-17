from __future__ import annotations

import os
from pathlib import Path

import cv2
from structlog.stdlib import BoundLogger

from splat_replay.application.interfaces import CapturePort
from splat_replay.domain.models import Frame, as_frame
from splat_replay.infrastructure.test_input import resolve_video_input_path


class VideoFileCapture(CapturePort):
    """動画ファイルからフレームを順次供給する。"""

    def __init__(self, source_path: Path, logger: BoundLogger) -> None:
        self._source_path = source_path
        self._logger = logger
        self._selected_path = resolve_video_input_path(source_path)
        self._capture: cv2.VideoCapture | None = None
        self._exhausted = False
        self._current_time_seconds: float | None = None
        self._fps = 0.0
        self._frame_stride = self._resolve_frame_stride()

    @property
    def selected_path(self) -> Path:
        return self._selected_path

    def setup(self) -> None:
        self.teardown()
        self._selected_path = resolve_video_input_path(self._source_path)
        capture = cv2.VideoCapture(str(self._selected_path))
        if not capture.isOpened():
            capture.release()
            raise RuntimeError(
                f"動画ファイルを開けませんでした: {self._selected_path}"
            )
        self._capture = capture
        self._exhausted = False
        self._fps = max(0.0, float(capture.get(cv2.CAP_PROP_FPS) or 0.0))
        self._current_time_seconds = 0.0
        self._logger.info(
            "動画ファイル入力を開始しました",
            video_path=str(self._selected_path),
            frame_stride=self._frame_stride,
        )

    def capture(self) -> Frame | None:
        if self._capture is None or self._exhausted:
            return None

        success, frame = self._capture.read()
        if not success or frame is None:
            self._exhausted = True
            self._logger.info(
                "動画ファイル入力が EOF に到達しました",
                video_path=str(self._selected_path),
            )
            return None

        self._current_time_seconds = self._resolve_current_time_seconds()
        self._skip_frames()
        return as_frame(frame)

    def current_time_seconds(self) -> float | None:
        return self._current_time_seconds

    def _resolve_current_time_seconds(self) -> float:
        if self._capture is None:
            return 0.0

        position_msec = float(self._capture.get(cv2.CAP_PROP_POS_MSEC) or 0.0)
        if position_msec > 0.0:
            return position_msec / 1000.0

        position_frames = float(
            self._capture.get(cv2.CAP_PROP_POS_FRAMES) or 0.0
        )
        if position_frames > 0.0 and self._fps > 0.0:
            current_frame_index = max(0.0, position_frames - 1.0)
            return current_frame_index / self._fps

        return self._current_time_seconds or 0.0

    def teardown(self) -> None:
        if self._capture is not None:
            self._capture.release()
            self._capture = None
        self._exhausted = False
        self._current_time_seconds = None
        self._fps = 0.0

    @staticmethod
    def _resolve_frame_stride() -> int:
        raw = os.getenv("SPLAT_REPLAY_E2E_FRAME_STRIDE", "1").strip()
        try:
            return max(1, int(raw))
        except ValueError:
            return 1

    def _skip_frames(self) -> None:
        if self._capture is None or self._frame_stride <= 1:
            return

        for _ in range(self._frame_stride - 1):
            if not self._capture.grab():
                self._exhausted = True
                return
