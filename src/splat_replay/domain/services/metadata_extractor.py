"""メタデータ抽出サービス。"""

from __future__ import annotations

from pathlib import Path

from splat_replay.domain.models.play import Play
from splat_replay.shared.logger import get_logger

logger = get_logger()


class MetadataExtractor:
    """動画や音声からメタデータを取得する。"""

    def extract_from_video(self, path: Path) -> Play:
        """動画ファイルからメタデータを抽出する。"""
        logger.info("メタデータ抽出", path=str(path))
        # 実装は後で追加
        raise NotImplementedError
