from typing import Optional

import cv2
from structlog.stdlib import BoundLogger

from splat_replay.application.interfaces import CapturePort
from splat_replay.domain.models import Frame, as_frame
from splat_replay.shared.config import RecordSettings


class Capture(CapturePort):
    def __init__(self, settings: RecordSettings, logger: BoundLogger):
        self.capture_index = settings.capture_index
        self.frame_width = settings.width
        self.frame_height = settings.height
        self.logger = logger
        self.video_capture: Optional[cv2.VideoCapture] = None

    def setup(self) -> None:
        self.video_capture = cv2.VideoCapture(self.capture_index)
        if not self.video_capture.isOpened():
            self.logger.error(
                "キャプチャデバイスを開けません",
                index=self.capture_index,
            )
            return
        self.video_capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.frame_width)
        self.video_capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.frame_height)

    def capture(self) -> Optional[Frame]:
        if self.video_capture is None:
            raise RuntimeError("キャプチャデバイスが初期化されていません")

        success, frame = self.video_capture.read()
        if not success:
            self.logger.warning("フレーム取得に失敗")
            return None
        return as_frame(frame)

    def teardown(self) -> None:
        """キャプチャデバイスを閉じる。"""
        if self.video_capture is not None and self.video_capture.isOpened():
            self.video_capture.release()
            self.logger.info("キャプチャデバイスを閉じました")
