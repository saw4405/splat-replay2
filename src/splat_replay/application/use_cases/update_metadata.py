"""メタデータ更新ユースケース。"""

from __future__ import annotations

from splat_replay.domain.models.play import Play
from splat_replay.domain.repositories.metadata_repo import MetadataRepository
from splat_replay.shared.logger import get_logger


class UpdateMetadataUseCase:
    """メタデータを保存・更新する。"""

    def __init__(self, repo: MetadataRepository) -> None:
        self.repo = repo
        self.logger = get_logger()

    def execute(self, match: Play) -> None:
        """メタデータを永続化する。"""
        self.logger.info("メタデータ保存")
        self.repo.save(match)
