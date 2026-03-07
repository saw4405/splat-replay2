"""Battle medal recognition port."""

from __future__ import annotations

from typing import Protocol

from splat_replay.domain.models import Frame


class BattleMedalRecognizerPort(Protocol):
    """結果画面から表彰の金銀個数を抽出する。"""

    async def count_medals(self, frame: Frame) -> tuple[int, int]: ...
