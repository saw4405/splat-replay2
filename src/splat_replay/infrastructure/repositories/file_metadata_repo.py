"""ファイルベースのメタデータリポジトリ。"""

from __future__ import annotations

from pathlib import Path

from splat_replay.domain.models.play import Play
from splat_replay.domain.repositories.metadata_repo import MetadataRepository
from splat_replay.shared.logger import get_logger

logger = get_logger()


class FileMetadataRepository(MetadataRepository):
    """JSON ファイルなどでメタデータを保存する実装。"""

    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir

    def save(self, match: Play) -> None:
        """メタデータを保存する。"""
        logger.info("メタデータ保存", match_id=match.id)
        raise NotImplementedError

    def list(self) -> list[Play]:
        """保存されているメタデータを取得する。"""
        logger.info("メタデータ一覧取得")
        raise NotImplementedError
