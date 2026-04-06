"""対戦履歴ポート定義。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from splat_replay.domain.models import RecordingMetadata

__all__ = [
    "BattleHistoryEntry",
    "BattleHistoryRepositoryPort",
]


@dataclass(frozen=True)
class BattleHistoryEntry:
    """1録画分の対戦履歴エントリ。

    source_video_id を識別子として持ち、メタデータ本体は
    動画サイドカーと同じ RecordingMetadata を使用する。
    """

    source_video_id: str
    metadata: RecordingMetadata


class BattleHistoryRepositoryPort(Protocol):
    """対戦履歴の永続化ポート。"""

    def find_by_source_video_id(
        self, source_video_id: str
    ) -> BattleHistoryEntry | None:
        """動画IDに紐づく履歴を取得する。"""
        ...

    def list_all(self) -> list[BattleHistoryEntry]:
        """全履歴を取得する。"""
        ...

    def upsert(self, entry: BattleHistoryEntry) -> None:
        """履歴を upsert する。"""
        ...
