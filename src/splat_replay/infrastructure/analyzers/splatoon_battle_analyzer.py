"""スプラトゥーン対戦モード用フレームアナライザー。"""

from __future__ import annotations

from typing import Tuple

import numpy as np

from splat_replay.infrastructure.analyzers.common.image_utils import (
    MatcherRegistry,
)
from splat_replay.shared.config import ImageMatchingSettings
from .plugin import AnalyzerPlugin


class BattleFrameAnalyzer(AnalyzerPlugin):
    """バトル向けフレーム解析ロジック。"""

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
        return self.registry.match("battle_start", frame)

    def detect_battle_abort(self, frame: np.ndarray) -> bool:
        return self.registry.match("battle_abort", frame)

    def detect_battle_finish(self, frame: np.ndarray) -> bool:
        return self.registry.match("battle_finish", frame)

    def detect_battle_finish_end(self, frame: np.ndarray) -> bool:
        return self.detect_battle_judgement(frame)

    def detect_battle_judgement(self, frame: np.ndarray) -> bool:
        return self.registry.match("battle_judgement_latter_half", frame)

    def detect_loading(self, frame: np.ndarray) -> bool:
        return self.registry.match("loading", frame)

    def detect_loading_end(self, frame: np.ndarray) -> bool:
        return self.registry.match("loading_end", frame)

    def extract_battle_judgement(self, frame: np.ndarray) -> str | None:
        """勝敗画面から勝敗を取得する。"""
        return self.registry.match_first_group("battle_judgements", frame)

    def detect_battle_result(self, frame: np.ndarray) -> bool:
        return self.registry.match("battle_result", frame)

    def extract_battle_match(self, frame: np.ndarray) -> str | None:
        """バトルマッチの種類を取得する。"""
        return self.registry.match_first_group("battle_matches", frame)

    def extract_battle_rule(self, frame: np.ndarray) -> str | None:
        """バトルルールを取得する。"""
        return self.registry.match_first_group("battle_rules", frame)

    def extract_battle_stage(self, frame: np.ndarray) -> str | None:
        """バトルステージを取得する。"""
        return self.registry.match_first_group("battle_stages", frame)

    def extract_battle_kill_record(self, frame: np.ndarray) -> Tuple[int, int, int] | None:
        """キルレコードを取得する。"""
        return (0, 0, 0)
