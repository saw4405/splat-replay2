"""サーモンラン用解析プラグイン。"""

from __future__ import annotations

import numpy as np

from splat_replay.infrastructure.analyzers.common.image_utils import MatcherRegistry
from splat_replay.shared.config import ImageMatchingSettings
from .plugin import AnalyzerPlugin


class SplatoonSalmonAnalyzer(AnalyzerPlugin):
    """サーモンラン向けの解析ロジック。"""

    def __init__(self, settings: ImageMatchingSettings) -> None:
        self.registry = MatcherRegistry(settings)

    def detect_battle_start(self, frame: np.ndarray) -> bool:
        return self.registry.match("salmon_start", frame)

    def detect_loading(self, frame: np.ndarray) -> bool:
        return self.registry.match("salmon_loading", frame)

    def detect_loading_end(self, frame: np.ndarray) -> bool:
        return self.registry.match("salmon_loading_end", frame)

    def detect_result(self, frame: np.ndarray) -> bool:
        return self.registry.match("salmon_result", frame)
