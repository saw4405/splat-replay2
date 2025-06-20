"""メタデータ抽出サービス。"""

from __future__ import annotations

from pathlib import Path

from splat_replay.domain.models.match import Match


class MetadataExtractor:
    """動画や音声からメタデータを取得する。"""

    def extract_from_video(self, path: Path) -> Match:
        """動画ファイルからメタデータを抽出する。"""
        # 実装は後で追加
        raise NotImplementedError
