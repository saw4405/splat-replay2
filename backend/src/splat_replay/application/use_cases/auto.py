"""オートユースケース。

Phase 9 リファクタリング:
- _run_edit_upload_sleep() メソッドを抽出（UploadUseCase との重複を削減）
"""

from __future__ import annotations

from splat_replay.application.interfaces import ConfigPort, LoggerPort
from splat_replay.application.services import (
    AutoEditor,
    AutoUploader,
    DeviceChecker,
    PowerManager,
)
from splat_replay.application.use_cases.auto_recording_use_case import (
    AutoRecordingUseCase,
)


class AutoUseCase:
    """録画からアップロードまで自動実行するユースケース。"""

    def __init__(
        self,
        logger: LoggerPort,
        config: ConfigPort,
        device_waiter: DeviceChecker,
        recording_use_case: AutoRecordingUseCase,
        editor: AutoEditor,
        uploader: AutoUploader,
        power: PowerManager,
    ) -> None:
        self.logger = logger
        self.config = config
        self.device_waiter = device_waiter
        self.recording_use_case = recording_use_case
        self.editor = editor
        self.uploader = uploader
        self.power = power

    async def wait_for_device(self, timeout: float | None = None) -> bool:
        """キャプチャデバイスの接続を待機する。"""
        return await self.device_waiter.wait_for_device_connection(timeout)

    async def execute(self) -> None:
        """録画→編集→アップロード→スリープの全自動実行。"""
        power_off = await self.recording_use_case.execute()
        if not power_off:
            self.logger.info(
                "電源オフ以外の理由で録画終了したため、録画後の編集をスキップします。"
            )
            return

        behavior_settings = self.config.get_behavior_settings()
        if not behavior_settings.edit_after_power_off:
            self.logger.info(
                "自動編集しない設定のため、録画後の編集をスキップします。"
            )
            return

        await self._run_edit_upload_sleep()

    async def _run_edit_upload_sleep(self) -> None:
        """編集→アップロード→スリープを実行する（UploadUseCase と共通処理）。"""
        await self.editor.execute()
        await self.uploader.execute()

        behavior_settings = self.config.get_behavior_settings()
        if not behavior_settings.sleep_after_upload:
            self.logger.info(
                "自動スリープしない設定のため、アップロード後のスリープをスキップします。"
            )
            return
        await self.power.sleep()
