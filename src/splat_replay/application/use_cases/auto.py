"""オートユースケース。"""

from __future__ import annotations

from splat_replay.application.services import (
    AutoEditor,
    AutoRecorder,
    AutoUploader,
    DeviceChecker,
    PowerManager,
)
from splat_replay.shared.config import BehaviorSettings
from splat_replay.shared.logger import get_logger


class AutoUseCase:
    """録画からアップロードまで自動実行するユースケース。"""

    def __init__(
        self,
        settings: BehaviorSettings,
        device_waiter: DeviceChecker,
        recorder: AutoRecorder,
        editor: AutoEditor,
        uploader: AutoUploader,
        power: PowerManager,
    ) -> None:
        self.logger = get_logger()
        self.settings = settings
        self.device_waiter = device_waiter
        self.recorder = recorder
        self.editor = editor
        self.uploader = uploader
        self.power = power

    async def wait_for_device(self, timeout: float | None = None) -> bool:
        """キャプチャデバイスの接続を待機する。"""
        return await self.device_waiter.wait_for_device_connection(timeout)

    async def execute(self) -> None:
        power_off = await self.recorder.execute()
        if not power_off:
            self.logger.info(
                "電源オフ以外の理由で録画終了したため、録画後の編集をスキップします。"
            )
            return
        if not self.settings.edit_after_power_off:
            self.logger.info(
                "自動編集しない設定のため、録画後の編集をスキップします。"
            )
            return
        await self.editor.execute()
        await self.uploader.execute()
        if not self.settings.sleep_after_upload:
            self.logger.info(
                "自動スリープしない設定のため、アップロード後のスリープをスキップします。"
            )
            return
        await self.power.sleep()
