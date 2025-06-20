"""動画アップロードユースケース。"""

from __future__ import annotations

from pathlib import Path

from splat_replay.application.dto.video_summary import VideoSummary
from splat_replay.application.interfaces import UploadPort
from splat_replay.shared.logger import get_logger


class UploadVideoUseCase:
    """動画をアップロードする。"""

    def __init__(self, uploader: UploadPort) -> None:
        self.uploader = uploader
        self.logger = get_logger()

    def execute(self, path: Path) -> VideoSummary:
        """動画をアップロードして結果を返す。"""
        self.logger.info("動画アップロード", path=str(path))
        video_id = self.uploader.upload(path)
        return VideoSummary(
            video_id=video_id, url=f"https://youtu.be/{video_id}"
        )
