from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Awaitable, Callable, Dict, List, Optional, Tuple

from splat_replay.application.interfaces import (
    VideoAssetRepositoryPort,
    VideoEditorPort,
)
from splat_replay.application.interfaces.data import FileStats
from splat_replay.domain.models import RecordingMetadata, VideoAsset


class AssetQueryService:
    """動画アセットに関する読み取り系/簡易更新系クエリの窓口。

    - すべてのI/Oは `asyncio.to_thread` 経由にして、イベントループを塞がない。
    - CommandBus へハンドラを提供するための `command_handlers` を持つ。
    """

    def __init__(
        self, repo: VideoAssetRepositoryPort, editor: VideoEditorPort
    ) -> None:
        self._repo = repo
        self._editor = editor

    def command_handlers(self) -> Dict[str, Callable[..., Awaitable[object]]]:
        """CommandBus へ登録するハンドラ群を返す。"""

        async def _list() -> List[VideoAsset]:
            return await asyncio.to_thread(self._repo.list_recordings)

        async def _list_with_length() -> List[
            Tuple[VideoAsset, float | None, FileStats | None]
        ]:
            assets = await asyncio.to_thread(self._repo.list_recordings)
            result: List[
                Tuple[VideoAsset, float | None, FileStats | None]
            ] = []
            for asset in assets:
                try:
                    length = await self._editor.get_video_length(asset.video)
                except Exception:
                    length = None
                stats = await asyncio.to_thread(
                    self._repo.get_file_stats, asset.video
                )
                result.append((asset, length, stats))
            return result

        async def _list_edited_with_length() -> List[
            Tuple[
                Path,
                float | None,
                dict[str, str] | None,
                FileStats | None,
                bool,
                bool,
            ]
        ]:
            paths = await asyncio.to_thread(self._repo.list_edited)
            result: List[
                Tuple[
                    Path,
                    float | None,
                    dict[str, str] | None,
                    FileStats | None,
                    bool,
                    bool,
                ]
            ] = []
            for path in paths:
                try:
                    length = await self._editor.get_video_length(path)
                except Exception:
                    length = None

                # メタデータをリポジトリ経由で読み込む
                md = await asyncio.to_thread(
                    self._repo.get_edited_metadata, path
                )
                stats = await asyncio.to_thread(
                    self._repo.get_file_stats, path
                )
                has_subtitle = await asyncio.to_thread(
                    self._repo.has_subtitle, path
                )
                has_thumbnail = await asyncio.to_thread(
                    self._repo.has_thumbnail, path
                )

                result.append(
                    (path, length, md, stats, has_subtitle, has_thumbnail)
                )
            return result

        async def _get_metadata(
            video_path: Path,
        ) -> Optional[dict[str, str | None]]:
            def work() -> Optional[dict[str, str | None]]:
                asset = self._repo.get_asset(video_path)
                if not asset or not asset.metadata:
                    return None
                raw = asset.metadata.to_dict()
                return {
                    key: value
                    if isinstance(value, str) or value is None
                    else str(value)
                    for key, value in raw.items()
                }

            return await asyncio.to_thread(work)

        async def _get_asset(video: Path) -> Optional[VideoAsset]:
            """VideoAsset を取得する。"""
            return await asyncio.to_thread(self._repo.get_asset, video)

        async def _save_edited_metadata(
            video: Path, metadata: RecordingMetadata
        ) -> None:
            """編集済みメタデータを保存する。"""
            return await asyncio.to_thread(
                self._repo.save_edited_metadata, video, metadata
            )

        async def _get_subtitle(video_path: Path) -> Optional[str]:
            return await asyncio.to_thread(self._repo.get_subtitle, video_path)

        async def _save_metadata(
            video_path: Path, metadata_dict: dict[str, str]
        ) -> bool:
            def work() -> bool:
                try:
                    from splat_replay.application.services.editing.metadata_parser import (
                        MetadataParser,
                    )

                    md = MetadataParser.from_dict(metadata_dict)
                    self._repo.save_edited_metadata(video_path, md)
                    return True
                except Exception:
                    return False

            return await asyncio.to_thread(work)

        async def _save_subtitle(video_path: Path, content: str) -> bool:
            return await asyncio.to_thread(
                self._repo.save_subtitle, video_path, content
            )

        async def _get_length(video_path: Path) -> Optional[float]:
            return await self._editor.get_video_length(video_path)

        async def _get_file_stats(path: Path) -> Optional[FileStats]:
            return await asyncio.to_thread(self._repo.get_file_stats, path)

        async def _has_subtitle(video_path: Path) -> bool:
            return await asyncio.to_thread(self._repo.has_subtitle, video_path)

        async def _has_thumbnail(video_path: Path) -> bool:
            return await asyncio.to_thread(
                self._repo.has_thumbnail, video_path
            )

        async def _delete_recording(video_path: Path) -> bool:
            return await asyncio.to_thread(
                self._repo.delete_recording, video_path
            )

        async def _get_recorded_dir() -> Path:
            return await asyncio.to_thread(self._repo.get_recorded_dir)

        async def _get_edited_dir() -> Path:
            return await asyncio.to_thread(self._repo.get_edited_dir)

        async def _delete_edited(video_path: Path) -> bool:
            return await asyncio.to_thread(
                self._repo.delete_edited, video_path
            )

        return {
            "asset.list": _list,
            "asset.list_with_length": _list_with_length,
            "asset.list_edited_with_length": _list_edited_with_length,
            "asset.get": _get_asset,
            "asset.get_metadata": _get_metadata,
            "asset.get_subtitle": _get_subtitle,
            "asset.save_metadata": _save_metadata,
            "asset.save_edited_metadata": _save_edited_metadata,
            "asset.save_subtitle": _save_subtitle,
            "asset.get_length": _get_length,
            "asset.get_file_stats": _get_file_stats,
            "asset.has_subtitle": _has_subtitle,
            "asset.has_thumbnail": _has_thumbnail,
            "asset.delete": _delete_recording,
            "asset.get_recorded_dir": _get_recorded_dir,
            "asset.get_edited_dir": _get_edited_dir,
            "asset.delete_edited": _delete_edited,
        }


__all__ = ["AssetQueryService"]
