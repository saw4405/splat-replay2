"""メタデータ更新ユースケース。"""

from __future__ import annotations

from splat_replay.domain.models.match import Match
from splat_replay.domain.repositories.metadata_repo import MetadataRepository


class UpdateMetadataUseCase:
    """メタデータを保存・更新する。"""

    def __init__(self, repo: MetadataRepository) -> None:
        self.repo = repo

    def execute(self, match: Match) -> None:
        """メタデータを永続化する。"""
        self.repo.save(match)
