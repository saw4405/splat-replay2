from __future__ import annotations

from collections.abc import Callable

from structlog.stdlib import BoundLogger

from splat_replay.application.interfaces import CapturePort
from splat_replay.infrastructure.adapters.capture.video_file_capture import (
    VideoFileCapture,
)
from splat_replay.infrastructure.test_input import (
    resolve_configured_test_video,
)


LiveCaptureFactory = Callable[[BoundLogger], CapturePort]


def _build_live_capture(logger: BoundLogger) -> CapturePort:
    """実機用 NDI キャプチャを必要になった時点で生成する。"""
    from splat_replay.infrastructure.adapters.capture.ndi_capture import (
        NDICapture,
    )

    return NDICapture(logger)


class AdaptiveCapture(CapturePort):
    """設定に応じて NDI と動画ファイル入力を切り替える。"""

    def __init__(
        self,
        logger: BoundLogger,
        *,
        live_capture_factory: LiveCaptureFactory | None = _build_live_capture,
    ) -> None:
        self._logger = logger
        self._live_capture_factory = live_capture_factory
        self._live_capture: CapturePort | None = None
        self._video_capture: VideoFileCapture | None = None
        self._active_capture: CapturePort | None = None
        self._active_key: str | None = None

    def _resolve_live_capture(self) -> CapturePort:
        if self._live_capture is not None:
            return self._live_capture
        if self._live_capture_factory is None:
            raise RuntimeError(
                "リプレイ実行では NDI キャプチャへフォールバックできません"
            )
        self._live_capture = self._live_capture_factory(self._logger)
        return self._live_capture

    def _resolve_capture(self) -> tuple[str, CapturePort]:
        resolved = resolve_configured_test_video()
        if resolved is None:
            return "live_capture", self._resolve_live_capture()

        key = str(resolved.selected_path)
        if (
            self._video_capture is None
            or str(self._video_capture.selected_path) != key
        ):
            self._video_capture = VideoFileCapture(
                resolved.selected_path, self._logger
            )
        return key, self._video_capture

    def _switch_capture(self, *, setup: bool) -> CapturePort:
        key, capture = self._resolve_capture()
        if key != self._active_key or capture is not self._active_capture:
            if self._active_capture is not None:
                self._active_capture.teardown()
            self._active_key = key
            self._active_capture = capture
            self._active_capture.setup()
        elif setup and self._active_capture is not None:
            self._active_capture.setup()
        if self._active_capture is None:
            raise RuntimeError("有効な CapturePort がありません")
        return self._active_capture

    def setup(self) -> None:
        self._switch_capture(setup=True)

    def capture(self):
        capture = self._switch_capture(setup=False)
        return capture.capture()

    def current_time_seconds(self) -> float | None:
        if self._active_capture is None:
            return None
        return self._active_capture.current_time_seconds()

    def teardown(self) -> None:
        if self._active_capture is not None:
            self._active_capture.teardown()
        self._active_capture = None
        self._active_key = None
