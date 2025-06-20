"""FFmpeg 実行アダプタ。"""

from __future__ import annotations

from pathlib import Path

from splat_replay.shared.logger import get_logger

logger = get_logger()


class FFmpegProcessor:
    """FFmpeg を呼び出して動画加工を行う。"""

    def merge(self, clips: list[Path]) -> Path:
        """動画を結合する。"""
        logger.info("FFmpeg 動画結合", clips=[str(c) for c in clips])
        raise NotImplementedError

    def embed_metadata(self, path: Path) -> None:
        """メタデータを埋め込む。"""
        logger.info("FFmpeg メタデータ埋め込み", path=str(path))
        raise NotImplementedError

    def embed_subtitle(self, path: Path, subtitle: Path) -> None:
        """字幕を動画へ追加する。"""
        logger.info("FFmpeg 字幕追加", path=str(path), subtitle=str(subtitle))
        raise NotImplementedError
