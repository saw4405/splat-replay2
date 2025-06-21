"""スプラトゥーン対戦モード用解析プラグイン。"""

from __future__ import annotations

import numpy as np

from splat_replay.infrastructure.analyzers.common.image_utils import MatcherRegistry
from splat_replay.shared.config import ImageMatchingSettings
from .plugin import AnalyzerPlugin


class SplatoonBattleAnalyzer(AnalyzerPlugin):
    """ナワバリ/ランクマッチ向け解析ロジック。"""

    def __init__(self, settings: ImageMatchingSettings) -> None:
        self.registry = MatcherRegistry(settings)

    def detect_battle_start(self, frame: np.ndarray) -> bool:
        return self.registry.match("battle_start", frame)

    def detect_loading(self, frame: np.ndarray) -> bool:
        return self.registry.match("loading", frame)

    def detect_loading_end(self, frame: np.ndarray) -> bool:
        return self.registry.match("loading_end", frame)

    def detect_result(self, frame: np.ndarray) -> bool:
        return self.registry.match("battle_result", frame)
