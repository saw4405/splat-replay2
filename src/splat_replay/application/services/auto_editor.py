from pathlib import Path

from splat_replay.shared.config import VideoEditSettings
from structlog.stdlib import BoundLogger
from splat_replay.domain.services.state_machine import Event, StateMachine
from splat_replay.application.interfaces import (
    VideoEditorPort,
    VideoAssetRepository,
    SubtitleEditorPort,
    ImageSelector,
)
from .editor import Editor


class AutoEditor:
    """録画済み動画の編集を行うサービス。"""

    def __init__(
        self,
        video_editor: VideoEditorPort,
        subtitle_editor: SubtitleEditorPort,
        image_selector: ImageSelector,
        settings: VideoEditSettings,
        repo: VideoAssetRepository,
        sm: StateMachine,
        logger: BoundLogger,
    ):
        self.repo = repo
        self.sm = sm
        self.logger = logger
        self.editor = Editor(
            video_editor, subtitle_editor, image_selector, settings, logger
        )

    def execute(self) -> list[Path]:
        self.logger.info("自動編集開始")
        self.sm.handle(Event.EDIT_START)
        assets = self.repo.list_recordings()

        results, edited_assets = self.editor.process(assets)

        edited: list[Path] = []
        for out in results:
            target = self.repo.save_edited(Path(out))
            self.logger.info("動画編集完了", path=str(target))
            edited.append(target)
        for asset in edited_assets:
            self.repo.delete_recording(asset.video)
        self.sm.handle(Event.EDIT_END)
        self.logger.info("自動編集終了")
        return edited
