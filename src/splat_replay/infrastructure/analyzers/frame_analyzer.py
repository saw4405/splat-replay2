"""ゲーム画面を解析するサービス。"""

from __future__ import annotations

from typing import Tuple

import numpy as np

from splat_replay.infrastructure.analyzers.common.image_utils import (
    MatcherRegistry,
)
from splat_replay.application.interfaces import FrameAnalyzerPort
from splat_replay.shared.config import ImageMatchingSettings
from splat_replay.domain.models import (
    GameMode,
    Match,
    RateBase,
    Result,
)
from splat_replay.infrastructure.analyzers import (
    BattleFrameAnalyzer,
    SalmonFrameAnalyzer,
)
from splat_replay.shared.logger import get_logger

logger = get_logger()


class FrameAnalyzer(FrameAnalyzerPort):
    """OpenCV を用いた画面解析処理を提供する。"""

    def __init__(
        self,
        battle_plugin: BattleFrameAnalyzer,
        salmon_plugin: SalmonFrameAnalyzer,
        settings: ImageMatchingSettings,
    ) -> None:
        """2 種類のプラグインと設定を受け取って初期化する。"""
        self.plugins = {
            GameMode.BATTLE: battle_plugin,
            GameMode.SALMON: salmon_plugin,
        }
        self.registry = MatcherRegistry(settings)

    def detect_power_off(self, frame: np.ndarray) -> bool:
        """Switch の電源 OFF を検出する。"""
        return self.registry.match("power_off", frame)

    def detect_match_select(self, frame: np.ndarray) -> bool:
        """マッチ選択画面かを判定する。"""
        return self.registry.match("match_select", frame)

    def extract_game_mode(self, frame: np.ndarray) -> GameMode | None:
        """ゲームモードを抽出する。"""
        for mode in GameMode:
            plugin = self.plugins.get(mode)
            if plugin is None:
                continue
            match = plugin.extract_match_select(frame)
            if match:
                return mode
        return None

    def extract_rate(self, frame: np.ndarray, mode: GameMode) -> RateBase | None:
        plugin = self.plugins.get(mode)
        if plugin is None:
            return None
        match = plugin.extract_match_select(frame)
        if match is None:
            return None
        return plugin.extract_rate(frame, match)

    def detect_matching_start(self, frame: np.ndarray) -> bool:
        """マッチング開始画面を検出する。"""
        return self.registry.match("matching_start", frame)

    def detect_schedule_change(self, frame: np.ndarray) -> bool:
        return self.registry.match("schedule_change", frame)

    def detect_session_start(self, frame: np.ndarray, mode: GameMode) -> bool:
        plugin = self.plugins.get(mode)
        if plugin is None:
            return False
        return plugin.detect_session_start(frame)

    def detect_session_abort(self, frame: np.ndarray, mode: GameMode) -> bool:
        plugin = self.plugins.get(mode)
        if plugin is None:
            return False
        return plugin.detect_session_abort(frame)

    def detect_session_finish(self, frame: np.ndarray, mode: GameMode) -> bool:
        plugin = self.plugins.get(mode)
        if plugin is None:
            return False
        return plugin.detect_session_finish(frame)

    def detect_session_finish_end(self, frame: np.ndarray, mode: GameMode) -> bool:
        plugin = self.plugins.get(mode)
        if plugin is None:
            return False
        return plugin.detect_session_finish_end(frame)

    def detect_session_judgement(self, frame: np.ndarray, mode: GameMode) -> bool:
        plugin = self.plugins.get(mode)
        if plugin is None:
            return False
        return plugin.detect_session_judgement(frame)

    def extract_session_judgement(self, frame: np.ndarray, mode: GameMode) -> str | None:
        """バトルの結果を抽出する。"""
        plugin = self.plugins.get(mode)
        if plugin is None:
            return None
        return plugin.extract_session_judgement(frame)

    def detect_loading(self, frame: np.ndarray) -> bool:
        """ローディング画面かどうか判定する。"""
        return self.registry.match("loading", frame)

    def detect_loading_end(self, frame: np.ndarray) -> bool:
        """ローディング終了を検出する。"""
        return not self.detect_loading(frame)

    def detect_session_result(self, frame: np.ndarray, mode: GameMode) -> bool:
        """結果画面を検出する。"""
        plugin = self.plugins.get(mode)
        if plugin is None:
            return False
        return plugin.detect_session_result(frame)

    def extract_session_result(self, frame: np.ndarray, mode: GameMode) -> Result | None:
        """バトルの結果を抽出する。"""
        plugin = self.plugins.get(mode)
        if plugin is None:
            return None

        return plugin.extract_session_result(frame)
