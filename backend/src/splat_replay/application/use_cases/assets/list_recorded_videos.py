"""録画済みビデオ一覧取得ユースケース。"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from splat_replay.application.dto import RecordedVideoDTO
from splat_replay.application.services.common.recorded_video_mapper import (
    build_recorded_video_dto,
)
from splat_replay.domain.models import RecordingMetadata

if TYPE_CHECKING:
    from splat_replay.application.interfaces import (
        LoggerPort,
        VideoAssetRepositoryPort,
        VideoEditorPort,
    )


class ListRecordedVideosUseCase:
    """録画済みビデオ一覧を取得するユースケース。

    責務：
    - 録画アセットの一覧を取得
    - RecordedVideoDTO に変換
    """

    def __init__(
        self,
        repository: VideoAssetRepositoryPort,
        logger: LoggerPort,
        base_dir: Path,
        video_editor: VideoEditorPort,
    ) -> None:
        self._repository = repository
        self._logger = logger
        self._base_dir = base_dir
        self._video_editor = video_editor

    async def execute(self) -> list[RecordedVideoDTO]:
        """録画済みビデオ一覧を取得。

        Returns:
            RecordedVideoDTO のリスト
        """

        assets = self._repository.list_recordings()

        items: list[RecordedVideoDTO] = []
        for asset in assets:
            # メタデータが無い場合はスキップ
            if asset.metadata is None:
                self._logger.warning(
                    f"メタデータが無いため録画をスキップします: {asset.video}"
                )
                continue

            # Type narrowing: この時点で metadata は RecordingMetadata 型
            metadata: RecordingMetadata = asset.metadata
            assert isinstance(metadata, RecordingMetadata), (
                "metadata は RecordingMetadata 型である必要があります"
            )

            items.append(
                await build_recorded_video_dto(
                    video_path=asset.video,
                    metadata=metadata,
                    base_dir=self._base_dir,
                    repository=self._repository,
                    video_editor=self._video_editor,
                    logger=self._logger,
                )
            )

        return items
