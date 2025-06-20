"""メタデータ保存リポジトリポート。"""

from __future__ import annotations

from typing import Protocol

from splat_replay.domain.models.match import Match


class MetadataRepository(Protocol):
    """メタデータの永続化インターフェース。"""

    def save(self, match: Match) -> None: ...

    def list(self) -> list[Match]: ...
