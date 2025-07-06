"""自動アップロードユースケース。"""

from __future__ import annotations

from splat_replay.application.interfaces import (
    UploadPort,
    VideoAssetRepository,
)
from splat_replay.shared.logger import get_logger


class AutoUploadUseCase:
    """編集済み動画を自動でアップロードする。"""

    def __init__(
        self, uploader: UploadPort, repo: VideoAssetRepository
    ) -> None:
        self.uploader = uploader
        self.repo = repo
        self.logger = get_logger()

    def execute(self) -> list[str]:
        """編集フォルダ内の動画をすべてアップロードする。"""
        self.logger.info("自動アップロード開始")
        ids: list[str] = []
        for video in self.repo.list_edited():
            self.logger.info("アップロード", path=str(video))
            ids.append(self.uploader.upload(video))
        return ids
