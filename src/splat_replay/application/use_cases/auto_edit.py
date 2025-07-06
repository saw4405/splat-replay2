"""自動編集ユースケース。"""

from __future__ import annotations

from pathlib import Path

from splat_replay.application.interfaces import (
    VideoEditorPort,
    VideoAssetRepository,
)
from splat_replay.domain.models import VideoAsset
from splat_replay.shared.logger import get_logger


class AutoEditUseCase:
    """録画済み動画を検索して編集を行う。"""

    def __init__(
        self,
        editor: VideoEditorPort,
        repo: VideoAssetRepository,
    ) -> None:
        self.editor = editor
        self.repo = repo
        self.logger = get_logger()

    def _collect_assets(self) -> list[VideoAsset]:
        return self.repo.list_recordings()

    def _process(self, assets: list[VideoAsset]) -> list[Path]:
        """動画アセットを編集して出力パスを返す。"""
        return self.editor.process(assets)

    def execute(self) -> list[Path]:
        """録画フォルダ内の動画を編集して返す。"""
        assets = self._collect_assets()
        results = self._process(assets)
        edited: list[Path] = []
        for out in results:
            target = self.repo.save_edited(Path(out))
            edited.append(target)
        return edited
