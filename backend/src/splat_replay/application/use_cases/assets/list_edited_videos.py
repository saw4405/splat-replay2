"""編集済みビデオ一覧取得ユースケース。"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from splat_replay.application.dto import EditedVideoDTO

if TYPE_CHECKING:
    from splat_replay.application.interfaces import (
        LoggerPort,
        VideoAssetRepositoryPort,
        VideoEditorPort,
    )


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
    ) -> None:
        self._repository = repository
        self._logger = logger
        self._base_dir = base_dir
        self._video_editor = video_editor

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
                )
            )

        return items
