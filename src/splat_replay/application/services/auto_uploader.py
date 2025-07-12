"""自動アップロードサービス。"""

from __future__ import annotations

from splat_replay.application.interfaces import (
    UploadPort,
    VideoAssetRepository,
)
from splat_replay.domain.services.state_machine import Event, StateMachine
from splat_replay.shared.logger import get_logger


class AutoUploader:
    """編集済み動画をアップロードするサービス。"""

    def __init__(
        self,
        uploader: UploadPort,
        repo: VideoAssetRepository,
        sm: StateMachine,
    ) -> None:
        self.uploader = uploader
        self.repo = repo
        self.sm = sm
        self.logger = get_logger()

    def execute(self) -> list[str]:
        self.logger.info("自動アップロード開始")
        self.sm.handle(Event.UPLOAD_START)
        ids: list[str] = []
        for video in self.repo.list_edited():
            self.logger.info("アップロード", path=str(video))
            id = self.uploader.upload(video)
            ids.append(id)
            self.repo.delete_edited(video)
        self.sm.handle(Event.UPLOAD_END)
        self.logger.info("自動アップロード終了")
        return ids
