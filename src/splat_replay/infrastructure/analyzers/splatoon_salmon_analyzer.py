"""サーモンラン用フレームアナライザー。"""

from __future__ import annotations

import numpy as np

from splat_replay.infrastructure.analyzers.common.image_utils import (
    MatcherRegistry,
)
from splat_replay.shared.config import ImageMatchingSettings
from .plugin import AnalyzerPlugin


class SalmonFrameAnalyzer(AnalyzerPlugin):
    """サーモンラン向けのフレーム解析ロジック。"""

    def __init__(self, settings: ImageMatchingSettings) -> None:
        self.registry = MatcherRegistry(settings)

    def detect_match_select(self, frame: np.ndarray) -> bool:
        return False

    def extract_rate(self, frame: np.ndarray) -> int | None:
        return None

    def detect_matching_start(self, frame: np.ndarray) -> bool:
        return False

    def detect_schedule_change(self, frame: np.ndarray) -> bool:
        return False

    def detect_battle_start(self, frame: np.ndarray) -> bool:
        return self.registry.match("salmon_start", frame)

    def detect_battle_abort(self, frame: np.ndarray) -> bool:
        return False

    def detect_loading(self, frame: np.ndarray) -> bool:
        return self.registry.match("salmon_loading", frame)

    def detect_loading_end(self, frame: np.ndarray) -> bool:
        return self.registry.match("salmon_loading_end", frame)

    def detect_finish(self, frame: np.ndarray) -> bool:
        return False

    def detect_finish_end(self, frame: np.ndarray) -> bool:
        return False

    def detect_judgement(self, frame: np.ndarray) -> str | None:
        return None

    def detect_result(self, frame: np.ndarray) -> bool:
        return self.registry.match("salmon_result", frame)
