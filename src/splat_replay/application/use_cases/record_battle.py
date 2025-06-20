"""バトル録画ユースケース。"""

from __future__ import annotations

from splat_replay.application.interfaces import VideoRecorder


class RecordBattleUseCase:
    """録画開始を担当する。"""

    def __init__(self, recorder: VideoRecorder) -> None:
        self.recorder = recorder

    def execute(self) -> None:
        """録画を開始する。"""
        self.recorder.start()
