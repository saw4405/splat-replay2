"""ポストゲーム処理ユースケース。"""

from __future__ import annotations

from pathlib import Path

from splat_replay.application.interfaces import VideoRecorder, VideoEditorPort


class ProcessPostGameUseCase:
    """録画停止と編集を行う。"""

    def __init__(
        self, recorder: VideoRecorder, editor: VideoEditorPort
    ) -> None:
        self.recorder = recorder
        self.editor = editor

    def execute(self) -> Path:
        """録画停止後に動画を編集する。"""
        path = self.recorder.stop()
        return self.editor.process(path)
