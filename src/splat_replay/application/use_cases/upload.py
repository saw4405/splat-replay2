"""アップロードユースケース。"""

from __future__ import annotations

from splat_replay.application.services import (
    AutoEditor,
    AutoUploader,
    PowerManager,
)
from splat_replay.shared.config import BehaviorSettings
from splat_replay.shared.logger import get_logger


class UploadUseCase:
    """自動編集と自動アップロードのみ実行するユースケース。"""

    def __init__(
        self,
        settings: BehaviorSettings,
        editor: AutoEditor,
        uploader: AutoUploader,
        power: PowerManager,
    ) -> None:
        self.logger = get_logger()
        self.settings = settings
        self.editor = editor
        self.uploader = uploader
        self.power = power

    async def execute(self) -> None:
        """動画編集とアップロードを行う。"""
        await self.editor.execute()
        await self.uploader.execute()
        if not self.settings.sleep_after_upload:
            self.logger.info(
                "自動スリープしない設定のため、アップロード後のスリープをスキップします。"
            )
            return
        await self.power.sleep()
