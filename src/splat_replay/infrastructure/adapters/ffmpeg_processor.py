"""FFmpeg 実行アダプタ。"""

from __future__ import annotations

from pathlib import Path


class FFmpegProcessor:
    """FFmpeg を呼び出して動画加工を行う。"""

    def merge(self, clips: list[Path]) -> Path:
        """動画を結合する。"""
        raise NotImplementedError

    def embed_metadata(self, path: Path) -> None:
        """メタデータを埋め込む。"""
        raise NotImplementedError

    def embed_subtitle(self, path: Path, subtitle: Path) -> None:
        """字幕を動画へ追加する。"""
        raise NotImplementedError
