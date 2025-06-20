"""ファイルベースのメタデータリポジトリ。"""

from __future__ import annotations

from pathlib import Path

from splat_replay.domain.models.match import Match
from splat_replay.domain.repositories.metadata_repo import MetadataRepository


class FileMetadataRepository(MetadataRepository):
    """JSON ファイルなどでメタデータを保存する実装。"""

    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir

    def save(self, match: Match) -> None:
        """メタデータを保存する。"""
        raise NotImplementedError

    def list(self) -> list[Match]:
        """保存されているメタデータを取得する。"""
        raise NotImplementedError
