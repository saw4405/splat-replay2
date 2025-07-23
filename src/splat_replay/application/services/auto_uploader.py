from structlog.stdlib import BoundLogger
from splat_replay.shared.config import UploadSettings
from splat_replay.domain.services.state_machine import Event, StateMachine
from splat_replay.application.interfaces import (
    VideoAssetRepository,
    UploadPort,
    VideoEditorPort,
)
from .uploader import Uploader


class AutoUploader:
    """編集済み動画をアップロードするサービス。"""

    def __init__(
        self,
        uploader: UploadPort,
        video_editor: VideoEditorPort,
        settings: UploadSettings,
        repo: VideoAssetRepository,
        sm: StateMachine,
        logger: BoundLogger,
    ):
        self.repo = repo
        self.sm = sm
        self.logger = logger
        self.uploader = Uploader(uploader, video_editor, settings, logger)

    def execute(self):
        self.logger.info("自動アップロード開始")
        self.sm.handle(Event.UPLOAD_START)
        for video in self.repo.list_edited():
            self.logger.info("アップロード", path=str(video))

            self.uploader.process(video)

            self.repo.delete_edited(video)
        self.sm.handle(Event.UPLOAD_END)
        self.logger.info("自動アップロード終了")
