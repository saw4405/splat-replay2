"""アップロードユースケース。

Phase 9 リファクタリング:
- AutoUseCase との重複コードを削減（共通処理を明確化）
"""

from __future__ import annotations

from splat_replay.application.interfaces import ConfigPort, LoggerPort
from splat_replay.application.services import (
    AutoEditor,
    AutoUploader,
    PowerManager,
)


class UploadUseCase:
    """自動編集と自動アップロードのみ実行するユースケース。

    録画をスキップし、編集→アップロード→スリープのみを実行する。
    AutoUseCase の一部処理と共通。
    """

    def __init__(
        self,
        logger: LoggerPort,
        config: ConfigPort,
        editor: AutoEditor,
        uploader: AutoUploader,
        power: PowerManager,
    ) -> None:
        self.logger = logger
        self.config = config
        self.editor = editor
        self.uploader = uploader
        self.power = power

    async def execute(self) -> None:
        """編集→アップロード→スリープを実行する（AutoUseCase._run_edit_upload_sleep() と同等）。"""
        await self.editor.execute()
        await self.uploader.execute()

        behavior_settings = self.config.get_behavior_settings()
        if not behavior_settings.sleep_after_upload:
            self.logger.info(
                "自動スリープしない設定のため、アップロード後のスリープをスキップします。"
            )
            return
        await self.power.sleep()
