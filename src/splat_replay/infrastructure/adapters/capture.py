from typing import Optional

import cv2

from structlog.stdlib import BoundLogger
from splat_replay.shared.config import RecordSettings
from splat_replay.domain.models import Frame, as_frame
from splat_replay.application.interfaces import CapturePort


class Capture(CapturePort):
    def __init__(self, settings: RecordSettings, logger: BoundLogger):
        self.logger = logger
        self.video_capture = cv2.VideoCapture(settings.capture_index)
        if not self.video_capture.isOpened():
            self.logger.error(
                "キャプチャデバイスを開けません",
                index=settings.capture_index,
            )
            raise RuntimeError("キャプチャデバイスの取得に失敗しました")
        self.video_capture.set(cv2.CAP_PROP_FRAME_WIDTH, settings.width)
        self.video_capture.set(cv2.CAP_PROP_FRAME_HEIGHT, settings.height)

    def capture(self) -> Optional[Frame]:
        success, frame = self.video_capture.read()
        if not success:
            self.logger.warning("フレーム取得に失敗")
            return None
        return as_frame(frame)

    def close(self):
        """キャプチャデバイスを閉じる。"""
        if self.video_capture.isOpened():
            self.video_capture.release()
            self.logger.info("キャプチャデバイスを閉じました")
