"""録画メタデータ更新ユースケース。"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING

from splat_replay.application.dto import (
    RecordedVideoDTO,
    RecordingMetadataPatchDTO,
)
from splat_replay.application.services.common.recorded_video_mapper import (
    build_recorded_video_dto,
)
from splat_replay.application.services.editing.metadata_parser import (
    MetadataParser,
)
from splat_replay.domain.models import (
    BattleResult,
    GameMode,
    RecordingMetadata,
    SalmonResult,
)
from splat_replay.domain.models.recording_metadata import (
    BATTLE_RESULT_REQUIRED_FIELDS,
    has_required_fields,
)

if TYPE_CHECKING:
    from splat_replay.application.interfaces import (
        LoggerPort,
        VideoAssetRepositoryPort,
        VideoEditorPort,
    )


class UpdateRecordedMetadataUseCase:
    """録画のメタデータを更新するユースケース。

    責務：
    - 録画ファイルのメタデータを更新
    - メタデータJSONファイルへの永続化
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

    async def execute(
        self, video_id: str, patch: RecordingMetadataPatchDTO
    ) -> RecordedVideoDTO:
        """録画メタデータを更新する。

        Args:
            video_id: 更新する動画の ID（base_dir からの相対パス、例: recorded/xxx.mp4）
            patch: 更新内容

        Returns:
            更新後の録画ビデオ詳細

        Raises:
            FileNotFoundError: 指定された動画が存在しない場合
            ValueError: 更新に必要な情報が不足している場合
        """
        video_path = self._base_dir / video_id

        if not video_path.exists():
            self._logger.warning(
                f"更新対象の録画ファイルが見つかりません: {video_path}"
            )
            raise FileNotFoundError(
                f"録画ファイルが見つかりません: {video_id}"
            )

        asset = self._repository.get_asset(video_path)
        if asset is None or asset.metadata is None:
            raise FileNotFoundError(f"メタデータが見つかりません: {video_id}")

        updates = patch.to_update_dict()
        updated_metadata = self._apply_updates(asset.metadata, updates)

        self._repository.save_edited_metadata(video_path, updated_metadata)
        self._logger.info(f"録画メタデータを更新しました: {video_path}")

        return await build_recorded_video_dto(
            video_path=video_path,
            metadata=updated_metadata,
            base_dir=self._base_dir,
            repository=self._repository,
            video_editor=self._video_editor,
            logger=self._logger,
        )

    def _apply_updates(
        self, current: RecordingMetadata, updates: dict[str, object]
    ) -> RecordingMetadata:
        if not updates:
            return current

        battle_fields = set(BATTLE_RESULT_REQUIRED_FIELDS)
        has_battle_updates = any(key in updates for key in battle_fields)

        if has_battle_updates and current.game_mode != GameMode.BATTLE:
            raise ValueError("バトル以外のメタデータは更新できません。")

        if has_battle_updates and isinstance(current.result, SalmonResult):
            raise ValueError("サーモンランのメタデータは更新できません。")

        updated = MetadataParser.parse_metadata_updates(current, updates)

        if has_battle_updates and current.result is None:
            if not has_required_fields(updates, BATTLE_RESULT_REQUIRED_FIELDS):
                raise ValueError(
                    "バトル結果を更新するには必要な項目が不足しています。"
                )
            result = BattleResult.from_dict(updates)
            updated = replace(updated, result=result)

        return updated
