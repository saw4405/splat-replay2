from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from splat_replay.application.interfaces import (
    VideoAssetRepository,
    VideoEditorPort,
)
from splat_replay.domain.models import RecordingMetadata, VideoAsset


class AssetQueryService:
    """動画アセットに関する読み取り系/簡易更新系クエリの窓口。

    - すべてのI/Oは `asyncio.to_thread` 経由にして、イベントループを塞がない。
    - CommandBus へハンドラを提供するための `command_handlers` を持つ。
    """

    def __init__(
        self, repo: VideoAssetRepository, editor: VideoEditorPort
    ) -> None:
        self._repo = repo
        self._editor = editor

    async def list_assets(self) -> List[VideoAsset]:
        return await asyncio.to_thread(self._repo.list_recordings)

    async def list_with_length(self) -> List[Tuple[VideoAsset, float | None]]:
        def work() -> List[Tuple[VideoAsset, float | None]]:
            result: List[Tuple[VideoAsset, float | None]] = []
            for a in self._repo.list_recordings():
                try:
                    length = self._editor.get_video_length(a.video)
                except Exception:
                    length = None
                result.append((a, length))
            return result

        return await asyncio.to_thread(work)

    async def list_edited_with_length(
        self,
    ) -> List[Tuple[Path, float | None, dict[str, str] | None]]:
        """List edited video files with their length and embedded metadata.

        Returns a list of triples: (edited_video_path, length_seconds_or_None, metadata_dict_or_None)
        """

        def work() -> List[Tuple[Path, float | None, dict[str, str] | None]]:
            result: List[Tuple[Path, float | None, dict[str, str] | None]] = []
            for p in self._repo.list_edited():
                try:
                    length = self._editor.get_video_length(p)
                except Exception:
                    length = None
                try:
                    md = self._editor.get_metadata(p)
                except Exception:
                    md = None
                result.append((p, length, md))
            return result

        return await asyncio.to_thread(work)

    async def get_metadata(self, video_path: Path) -> Optional[dict]:
        def work() -> Optional[dict]:
            asset = self._repo.get_asset(video_path)
            return (
                asset.metadata.to_dict() if asset and asset.metadata else None
            )

        return await asyncio.to_thread(work)

    async def save_metadata(
        self, video_path: Path, metadata_dict: dict
    ) -> bool:
        def work() -> bool:
            try:
                md = RecordingMetadata.from_dict(metadata_dict)
                self._repo.save_edited_metadata(video_path, md)
                return True
            except Exception:
                return False

        return await asyncio.to_thread(work)

    async def get_length(self, video_path: Path) -> float | None:
        def work() -> float | None:
            try:
                return self._editor.get_video_length(video_path)
            except Exception:
                return None

        return await asyncio.to_thread(work)

    async def delete(self, video_path: Path) -> bool:
        def work() -> bool:
            try:
                self._repo.delete_recording(video_path)
                return True
            except Exception:
                return False

        return await asyncio.to_thread(work)

    async def get_recorded_dir(self) -> Path:
        return await asyncio.to_thread(self._repo.get_recorded_dir)

    async def get_edited_dir(self) -> Path:
        return await asyncio.to_thread(self._repo.get_edited_dir)

    async def delete_edited(self, video_path: Path) -> bool:
        def work() -> bool:
            try:
                self._repo.delete_edited(video_path)
                return True
            except Exception:
                return False

        return await asyncio.to_thread(work)

    def command_handlers(self) -> Dict[str, Callable[..., object]]:
        """CommandBus へ登録するハンドラ群を返す。"""

        async def _list():
            return await self.list_assets()

        async def _list_with_length():
            return await self.list_with_length()

        async def _list_edited_with_length():
            return await self.list_edited_with_length()

        async def _get_metadata(video_path: Path):
            return await self.get_metadata(video_path)

        async def _save_metadata(video_path: Path, metadata_dict: dict):
            return await self.save_metadata(video_path, metadata_dict)

        async def _get_length(video_path: Path):
            return await self.get_length(video_path)

        async def _delete(video_path: Path):
            return await self.delete(video_path)

        async def _get_recorded_dir():
            return await self.get_recorded_dir()

        async def _get_edited_dir():
            return await self.get_edited_dir()

        async def _delete_edited(video_path: Path):
            return await self.delete_edited(video_path)

        return {
            "asset.list": _list,
            "asset.list_with_length": _list_with_length,
            "asset.list_edited_with_length": _list_edited_with_length,
            "asset.get_metadata": _get_metadata,
            "asset.save_metadata": _save_metadata,
            "asset.get_length": _get_length,
            "asset.delete": _delete,
            "asset.get_recorded_dir": _get_recorded_dir,
            "asset.get_edited_dir": _get_edited_dir,
            "asset.delete_edited": _delete_edited,
        }


__all__ = ["AssetQueryService"]
