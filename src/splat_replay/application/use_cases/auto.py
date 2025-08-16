"""オートユースケース。"""

from __future__ import annotations

from splat_replay.application.services import (
    AutoEditor,
    AutoRecorder,
    AutoUploader,
    DeviceWaiter,
    PowerManager,
)


class AutoUseCase:
    """録画からアップロードまで自動実行するユースケース。"""

    def __init__(
        self,
        device_waiter: DeviceWaiter,
        recorder: AutoRecorder,
        editor: AutoEditor,
        uploader: AutoUploader,
        power: PowerManager,
    ) -> None:
        self.device_waiter = device_waiter
        self.recorder = recorder
        self.editor = editor
        self.uploader = uploader
        self.power = power

    async def wait_for_device(self, timeout: float | None = None) -> bool:
        """キャプチャデバイスの接続を待機する。"""
        return await self.device_waiter.execute(timeout)

    async def record(self) -> None:
        await self.recorder.execute()

    async def edit(self) -> None:
        await self.editor.execute()

    async def update(self) -> None:
        await self.uploader.execute()

    async def sleep(self) -> None:
        await self.power.sleep()
