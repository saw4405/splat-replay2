"""バトル録画ユースケース。"""

from __future__ import annotations

from splat_replay.application.interfaces import VideoRecorder
from splat_replay.shared.logger import get_logger


class RecordBattleUseCase:
    """録画開始を担当する。"""

    def __init__(self, recorder: VideoRecorder) -> None:
        self.recorder = recorder
        self.logger = get_logger()

    def execute(self) -> None:
        """録画を開始する。"""
        self.logger.info("録画開始")
        self.recorder.start()
