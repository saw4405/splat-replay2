"""オートユースケース。"""

from __future__ import annotations

from splat_replay.application.services import (
    EnvironmentInitializer,
    AutoRecorder,
    AutoEditor,
    AutoUploader,
    PowerManager,
)


class AutoUseCase:
    """録画からアップロードまで自動実行するユースケース。"""

    def __init__(
        self,
        initializer: EnvironmentInitializer,
        recorder: AutoRecorder,
        editor: AutoEditor,
        uploader: AutoUploader,
        power: PowerManager,
    ) -> None:
        self.initializer = initializer
        self.recorder = recorder
        self.editor = editor
        self.uploader = uploader
        self.power = power

    async def execute(self, timeout: float | None = None) -> None:
        """録画準備からスリープまでを実行する。"""
        import asyncio

        await self.initializer.execute(timeout)
        await asyncio.to_thread(self.recorder.execute)
        await asyncio.to_thread(self.editor.execute)
        await asyncio.to_thread(self.uploader.execute)
        await asyncio.to_thread(self.power.sleep)
