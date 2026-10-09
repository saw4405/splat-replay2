"""動画ファイルをブラウザー再生用の形式へ準備する。"""

from __future__ import annotations

from pathlib import Path

from splat_replay.application.interfaces import VideoPreviewPort


class VideoPreviewService:
    """MP4 はそのまま使い、MKV はポート経由で MP4 化する。"""

    def __init__(self, preview_port: VideoPreviewPort) -> None:
        self._preview_port = preview_port

    async def prepare(self, source: Path) -> Path:
        """動画をブラウザー再生可能な MP4 として返す。"""
        suffix = source.suffix.lower()
        if suffix == ".mp4":
            return source
        if suffix != ".mkv":
            raise ValueError(f"Unsupported video preview extension: {suffix}")
        return await self._preview_port.create_mp4_preview(source)

    async def close(self) -> None:
        """アプリ終了時に一時ファイルと実行中処理を破棄する。"""
        await self._preview_port.close()
