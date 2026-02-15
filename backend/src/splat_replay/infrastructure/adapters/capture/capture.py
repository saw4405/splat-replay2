from typing import List, Optional

import cv2
from structlog.stdlib import BoundLogger

from splat_replay.application.interfaces import CapturePort
from splat_replay.domain.config import RecordSettings
from splat_replay.domain.models import Frame, as_frame


def _list_capture_devices_via_dshow() -> List[str]:
    """DirectShow からキャプチャデバイスを取得する。"""
    try:
        from pygrabber.dshow_graph import FilterGraph
    except Exception:
        return []

    graph = FilterGraph()
    return graph.get_input_devices()


class Capture(CapturePort):
    @staticmethod
    def list_capture_devices() -> List[str]:
        """DirectShowのビデオ入力デバイス名一覧を取得"""
        return _list_capture_devices_via_dshow()

    @staticmethod
    def get_camera_index_by_name(target_name: str) -> Optional[int]:
        """
        キャプチャデバイス名(部分一致OK)から OpenCV のインデックス(0,1,2,...)を返す。
        多くの環境で DirectShow 列挙順と OpenCV のインデックスが一致する前提。
        """
        devices = Capture.list_capture_devices()
        for i, name in enumerate(devices):
            if target_name.lower() in name.lower():
                return i
        return None

    def __init__(self, settings: RecordSettings, logger: BoundLogger):
        try:
            self.capture_index = int(settings.capture_device)
        except ValueError:
            index = Capture.get_camera_index_by_name(settings.capture_device)
            if index is None:
                raise ValueError(
                    f"指定されたキャプチャデバイスが見つかりません: {settings.capture_device}"
                )
            self.capture_index = index

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
            self.logger.warning("Frame capture failed")
            return None
        return as_frame(frame)

    def teardown(self) -> None:
        """キャプチャデバイスを閉じる。"""
        if self.video_capture is not None and self.video_capture.isOpened():
            self.video_capture.release()
            self.logger.info("キャプチャデバイスを閉じました")
