"""編集済みビデオ一覧取得ユースケース。"""

from __future__ import annotations

import asyncio
import datetime as dt
from pathlib import Path
from typing import TYPE_CHECKING

from splat_replay.application.dto import EditedVideoDTO
from splat_replay.application.services.editing.title_description_generator import (
    TitleDescriptionGenerator,
)
from splat_replay.application.services.editing.video_grouping_service import (
    VideoGroupingService,
)

if TYPE_CHECKING:
    from splat_replay.application.interfaces import (
        ConfigPort,
        FileSystemPort,
        LoggerPort,
        VideoAssetRepositoryPort,
        VideoEditorPort,
    )
    from splat_replay.application.services.editing import ThumbnailGenerator
    from splat_replay.domain.models import VideoAsset


class ListEditedVideosUseCase:
    """編集済みビデオ一覧を取得するユースケース。

    責務：
    - 編集済みアセットの一覧を取得
    - EditedVideoDTO に変換
    """

    def __init__(
        self,
        repository: VideoAssetRepositoryPort,
        logger: LoggerPort,
        base_dir: Path,
        video_editor: VideoEditorPort,
        config: ConfigPort | None = None,
        thumbnail_generator: ThumbnailGenerator | None = None,
        file_system: FileSystemPort | None = None,
    ) -> None:
        self._repository = repository
        self._logger = logger
        self._base_dir = base_dir
        self._video_editor = video_editor
        self._thumbnail_generator = thumbnail_generator
        self._file_system = file_system
        self._grouping = VideoGroupingService(logger)
        self._title_generator = (
            TitleDescriptionGenerator(logger, config, video_editor)
            if config is not None
            else None
        )

    async def execute(self) -> list[EditedVideoDTO]:
        """編集済みビデオ一覧を取得。

        Returns:
            EditedVideoDTO のリスト
        """

        videos = self._repository.list_edited()

        items: list[EditedVideoDTO] = []
        for video_path in videos:
            # base_dir からの相対パスに変換（edited/xxx.mkv）
            try:
                relative_path = video_path.relative_to(self._base_dir)
            except ValueError:
                # base_dir 外のファイルは警告してスキップ
                self._logger.warning(
                    "base_dir 外のファイルはスキップします",
                    video=str(video_path),
                    base_dir=str(self._base_dir),
                )
                continue

            video_id = str(relative_path.as_posix())

            metadata = self._repository.get_edited_metadata(video_path)
            metadata_payload: dict[str, str | None] | None = None
            title: str | None = None
            description: str | None = None
            if metadata:
                metadata_payload = {
                    key: value or None for key, value in metadata.items()
                }
                title = metadata.get("title") or None
                description = metadata.get("description") or None

            duration_seconds: float | None = None
            try:
                duration_seconds = await self._video_editor.get_video_length(
                    video_path
                )
            except Exception as exc:
                self._logger.warning(
                    "動画の長さ取得失敗",
                    video=str(video_path),
                    error=str(exc),
                )

            file_stats = self._repository.get_file_stats(video_path)
            updated_at: str | None = None
            if file_stats is not None:
                from datetime import datetime

                updated_at = datetime.fromtimestamp(
                    file_stats.updated_at
                ).isoformat()

            items.append(
                EditedVideoDTO(
                    video_id=video_id,
                    path=str(video_path),
                    filename=video_path.name,
                    duration_seconds=duration_seconds,
                    has_subtitle=self._repository.has_subtitle(video_path),
                    has_thumbnail=self._repository.has_thumbnail(video_path),
                    metadata=metadata_payload,
                    updated_at=updated_at,
                    size_bytes=file_stats.size_bytes if file_stats else None,
                    title=title or video_path.stem,
                    description=description,
                    thumbnail_source="edited",
                    thumbnail_filename=video_path.name,
                )
            )

        items.extend(await self._build_pending_items())
        return items

    async def _build_pending_items(self) -> list[EditedVideoDTO]:
        assets = self._repository.list_recordings()
        groups = self._grouping.group_by_timeslot(assets)

        items: list[EditedVideoDTO] = []
        for key, group in groups.items():
            if not group:
                continue

            day, time_slot, match_name, rule_name = key
            sorted_group = self._sort_group(group)
            recorded_video_ids = self._recorded_video_ids(sorted_group)
            if not recorded_video_ids:
                continue

            filename = (
                f"{day.strftime('%Y%m%d')}_{time_slot.strftime('%H')}_"
                f"{match_name}_{rule_name}{sorted_group[0].video.suffix}"
            )
            target_video = self._repository.get_edited_dir() / filename
            title, description = await self._generate_title_description(
                sorted_group,
                day,
                time_slot,
                match_name,
                rule_name,
            )
            has_thumbnail = await self._ensure_pending_thumbnail(
                target_video,
                sorted_group,
            )
            updated_at = self._group_updated_at(sorted_group)

            items.append(
                EditedVideoDTO(
                    video_id=f"pending/{Path(filename).stem}",
                    path="",
                    filename=filename,
                    duration_seconds=None,
                    has_subtitle=any(
                        self._repository.has_subtitle(asset.video)
                        for asset in sorted_group
                    ),
                    has_thumbnail=has_thumbnail,
                    metadata={
                        "schedule": dt.datetime.combine(
                            day,
                            time_slot,
                        ).isoformat(),
                        "recorded_count": str(len(sorted_group)),
                        "match": match_name,
                        "rule": rule_name,
                    },
                    updated_at=updated_at,
                    size_bytes=self._group_size_bytes(sorted_group),
                    title=title,
                    description=description,
                    source="pending",
                    playable=False,
                    recorded_video_ids=recorded_video_ids,
                    thumbnail_source="edited",
                    thumbnail_filename=filename if has_thumbnail else None,
                )
            )

        return items

    @staticmethod
    def _sort_group(group: list[VideoAsset]) -> list[VideoAsset]:
        return sorted(
            group,
            key=lambda asset: (
                asset.metadata.started_at
                if asset.metadata and asset.metadata.started_at
                else dt.datetime.min
            ),
        )

    def _recorded_video_ids(
        self,
        group: list[VideoAsset],
    ) -> tuple[str, ...]:
        video_ids: list[str] = []
        for asset in group:
            try:
                relative_path = asset.video.relative_to(self._base_dir)
            except ValueError:
                self._logger.warning(
                    "base_dir 外の録画済みファイルはスキップしました",
                    video=str(asset.video),
                    base_dir=str(self._base_dir),
                )
                continue
            video_ids.append(relative_path.as_posix())
        return tuple(video_ids)

    async def _generate_title_description(
        self,
        group: list[VideoAsset],
        day: dt.date,
        time_slot: dt.time,
        match_name: str,
        rule_name: str,
    ) -> tuple[str, str]:
        if self._title_generator is not None:
            try:
                title, description = await self._title_generator.generate(
                    group,
                    day,
                    time_slot,
                )
                if title or description:
                    return title, description
            except Exception as exc:
                self._logger.warning(
                    "未生成グループのタイトル・説明生成に失敗しました",
                    error=str(exc),
                )

        return (
            f"{match_name} / {rule_name}",
            f"{day.strftime('%Y/%m/%d')} {time_slot.strftime('%H')}時～\n"
            f"録画済動画: {len(group)}件",
        )

    def _find_thumbnail_asset(
        self,
        group: list[VideoAsset],
    ) -> VideoAsset | None:
        for asset in group:
            if self._repository.has_thumbnail(asset.video):
                return asset
        return None

    async def _ensure_pending_thumbnail(
        self,
        target_video: Path,
        group: list[VideoAsset],
    ) -> bool:
        if self._repository.has_thumbnail(
            target_video
        ) and not self._pending_thumbnail_is_stale(target_video, group):
            return True

        if (
            self._thumbnail_generator is not None
            and self._file_system is not None
        ):
            try:
                generated_path = await asyncio.to_thread(
                    self._thumbnail_generator.create,
                    group,
                )
                if generated_path and self._file_system.is_file(
                    generated_path
                ):
                    try:
                        data = await asyncio.to_thread(
                            self._file_system.read_bytes,
                            generated_path,
                        )
                        saved = await asyncio.to_thread(
                            self._repository.save_edited_thumbnail,
                            target_video,
                            data,
                        )
                        if saved:
                            return True
                    finally:
                        await asyncio.to_thread(
                            self._file_system.unlink,
                            generated_path,
                            missing_ok=True,
                        )
            except Exception as exc:
                self._logger.warning(
                    "未生成グループのサムネイル生成に失敗しました",
                    target=str(target_video),
                    error=str(exc),
                )

        return await self._copy_representative_thumbnail(target_video, group)

    async def _copy_representative_thumbnail(
        self,
        target_video: Path,
        group: list[VideoAsset],
    ) -> bool:
        if self._file_system is None:
            return self._repository.has_thumbnail(target_video)

        thumbnail_asset = self._find_thumbnail_asset(group)
        if thumbnail_asset is None or thumbnail_asset.thumbnail is None:
            return False

        try:
            data = await asyncio.to_thread(
                self._file_system.read_bytes,
                thumbnail_asset.thumbnail,
            )
            return await asyncio.to_thread(
                self._repository.save_edited_thumbnail,
                target_video,
                data,
            )
        except Exception as exc:
            self._logger.warning(
                "代表録画サムネイルの保存に失敗しました",
                target=str(target_video),
                source=str(thumbnail_asset.thumbnail),
                error=str(exc),
            )
            return False

    def _pending_thumbnail_is_stale(
        self,
        target_video: Path,
        group: list[VideoAsset],
    ) -> bool:
        thumbnail_stats = self._repository.get_file_stats(
            target_video.with_suffix(".png")
        )
        if thumbnail_stats is None:
            return True

        for asset in group:
            for source in (
                asset.video,
                asset.video.with_suffix(".png"),
                asset.video.with_suffix(".json"),
            ):
                source_stats = self._repository.get_file_stats(source)
                if (
                    source_stats is not None
                    and source_stats.updated_at > thumbnail_stats.updated_at
                ):
                    return True
        return False

    def _group_updated_at(self, group: list[VideoAsset]) -> str | None:
        timestamps: list[float] = []
        for asset in group:
            file_stats = self._repository.get_file_stats(asset.video)
            if file_stats is not None:
                timestamps.append(file_stats.updated_at)

        if timestamps:
            return dt.datetime.fromtimestamp(max(timestamps)).isoformat()

        started_at_values = [
            asset.metadata.started_at
            for asset in group
            if asset.metadata and asset.metadata.started_at
        ]
        if started_at_values:
            return max(started_at_values).isoformat()
        return None

    def _group_size_bytes(self, group: list[VideoAsset]) -> int | None:
        total = 0
        found = False
        for asset in group:
            file_stats = self._repository.get_file_stats(asset.video)
            if file_stats is None:
                continue
            total += file_stats.size_bytes
            found = True
        return total if found else None
