"""メタデータ保存リポジトリポート。"""

from __future__ import annotations

from typing import Protocol

from splat_replay.domain.models.play import Play


class MetadataRepository(Protocol):
    """メタデータの永続化インターフェース。"""

    def save(self, match: Play) -> None: ...

    def list(self) -> list[Play]: ...
