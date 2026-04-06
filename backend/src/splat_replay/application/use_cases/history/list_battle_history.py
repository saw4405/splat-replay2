"""対戦履歴一覧取得ユースケース。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from splat_replay.application.interfaces import BattleHistoryEntry

if TYPE_CHECKING:
    from splat_replay.application.interfaces import BattleHistoryRepositoryPort


class ListBattleHistoryUseCase:
    """対戦履歴の一覧を取得するユースケース。

    責務：
    - 永続化された対戦履歴エントリを返す
    """

    def __init__(
        self,
        repository: BattleHistoryRepositoryPort,
    ) -> None:
        self._repository = repository

    def execute(self) -> list[BattleHistoryEntry]:
        """全対戦履歴を取得する。

        Returns:
            BattleHistoryEntry のリスト
        """
        return self._repository.list_all()
