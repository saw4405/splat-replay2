from typing import Optional

import cv2
from cyndilib.finder import Finder, Source
from cyndilib.receiver import Receiver
from cyndilib.video_frame import VideoFrameSync
from cyndilib.wrapper.ndi_recv import RecvBandwidth, RecvColorFormat
from structlog.stdlib import BoundLogger

from splat_replay.application.interfaces import CapturePort
from splat_replay.domain.models import Frame, as_frame


class NDICapture(CapturePort):
    def __init__(self, logger: BoundLogger):
        self.logger = logger

        self.finder = Finder()
        self.receiver = Receiver(
            color_format=RecvColorFormat.RGBX_RGBA,  # OpenCVへ渡しやすい（後でBGRに変換）
            bandwidth=RecvBandwidth.highest,  # ネットワーク/CPUに応じて後述の調整可
        )
        self.source: Optional[Source] = None
        self.video_frame = VideoFrameSync()
        self.receiver.frame_sync.set_video_frame(self.video_frame)
        self.finder.set_change_callback(self.on_finder_change)

    def on_finder_change(self) -> None:
        names = self.finder.get_source_names()
        if names and self.source is None:
            self.source = self.finder.get_source(names[0])
            self.receiver.set_source(self.source)

    def setup(self) -> None:
        import time

        self.finder.open()

        # ソースが見つかって接続されるまで待機
        max_wait = 10.0  # 最大10秒待機
        wait_interval = 0.1
        elapsed = 0.0

        while elapsed < max_wait:
            if self.source is not None and self.receiver.is_connected():
                break
            time.sleep(wait_interval)
            elapsed += wait_interval

    def capture(self) -> Optional[Frame]:
        if self.receiver.is_connected():
            self.receiver.frame_sync.capture_video()  # 同期キャプチャ（安定）
            if min(self.video_frame.xres, self.video_frame.yres) != 0:
                raw_frame = self.video_frame.get_array()
                frame_reshaped = raw_frame.reshape(
                    self.video_frame.yres, self.video_frame.xres, 4
                )
                frame_bgr = cv2.cvtColor(frame_reshaped, cv2.COLOR_RGBA2BGR)
                return as_frame(frame_bgr)
        return None

    def teardown(self) -> None:
        """キャプチャデバイスを閉じる。"""
        if self.receiver.is_connected():
            self.receiver.disconnect()
        self.finder.close()
