"""DI Container: Domain services registration.

Phase 3 リファクタリング - ドメインサービスの登録を分離。
"""

from __future__ import annotations

import punq

from splat_replay.domain.services import (
    BattleFrameAnalyzer,
    FrameAnalyzer,
    SalmonFrameAnalyzer,
)


def register_domain_services(container: punq.Container) -> None:
    """ドメインサービスを DI コンテナに登録する。"""
    container.register(FrameAnalyzer, FrameAnalyzer)
    container.register(BattleFrameAnalyzer, BattleFrameAnalyzer)
    container.register(SalmonFrameAnalyzer, SalmonFrameAnalyzer)
