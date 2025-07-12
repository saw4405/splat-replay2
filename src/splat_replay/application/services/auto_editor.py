"""自動編集サービス。"""

from __future__ import annotations

from pathlib import Path

from splat_replay.application.interfaces import (
    VideoEditorPort,
    VideoAssetRepository,
)
from splat_replay.domain.services.state_machine import Event, StateMachine
from splat_replay.domain.models import VideoAsset
from splat_replay.shared.logger import get_logger


class AutoEditor:
    """録画済み動画の編集を行うサービス。"""

    def __init__(
        self,
        editor: VideoEditorPort,
        repo: VideoAssetRepository,
        sm: StateMachine,
    ) -> None:
        self.editor = editor
        self.repo = repo
        self.sm = sm
        self.logger = get_logger()

    def _collect_assets(self) -> list[VideoAsset]:
        return self.repo.list_recordings()

    def _process(self, assets: list[VideoAsset]) -> list[Path]:
        return self.editor.process(assets)

    def execute(self) -> list[Path]:
        self.logger.info("自動編集開始")
        self.sm.handle(Event.EDIT_START)
        assets = self._collect_assets()
        results = self._process(assets)
        edited: list[Path] = []
        for out in results:
            target = self.repo.save_edited(Path(out))
            edited.append(target)
        self.sm.handle(Event.EDIT_END)
        return edited
