"""Replay 用の表彰認識アダプタ。"""

from __future__ import annotations

from splat_replay.domain.models import Frame
from splat_replay.domain.ports import BattleMedalRecognizerPort
from splat_replay.infrastructure.test_input import (
    resolve_replay_battle_medal_observation,
)


class ReplayBattleMedalRecognizerAdapter(BattleMedalRecognizerPort):
    """Sidecar の表彰観測を返し、実テンプレート照合へはフォールバックしない。"""

    async def count_medals(self, frame: Frame) -> tuple[int, int]:
        _ = frame
        observation = resolve_replay_battle_medal_observation()
        return observation.gold, observation.silver
