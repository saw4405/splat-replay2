"""ゲーム画面を解析するサービス。"""

from __future__ import annotations

import numpy as np

from splat_replay.infrastructure.analyzers.common.image_utils import (
    MatcherRegistry,
)

from splat_replay.shared.config import ImageMatchingSettings
from .plugin import AnalyzerPlugin
from splat_replay.domain.models import GameMode

from splat_replay.shared.logger import get_logger

logger = get_logger()


class FrameAnalyzer:
    """OpenCV を用いた画面解析処理を提供する。"""

    def __init__(
        self,
        battle_plugin: AnalyzerPlugin,
        salmon_plugin: AnalyzerPlugin,
        settings: ImageMatchingSettings,
    ) -> None:
        """2 種類のプラグインと設定を受け取って初期化する。"""
        self.plugins = {
            GameMode.BATTLE: battle_plugin,
            GameMode.SALMON: salmon_plugin,
        }
        self.mode = GameMode.UNKNOWN
        self.registry = MatcherRegistry(settings)

    def set_mode(self, mode: GameMode) -> None:
        """解析対象モードを外部から設定する。"""
        self.mode = mode

    def reset_mode(self) -> None:
        """モードを未確定状態へ戻す。"""
        self.mode = GameMode.UNKNOWN

    def detect_power_off(self, frame: np.ndarray) -> bool:
        """Switch の電源 OFF を検出する。"""
        return self.registry.match("power_off", frame)

    def detect_match_select(self, frame: np.ndarray) -> bool:
        """マッチ選択画面かを判定しモードを設定する。"""
        if self.plugins[GameMode.BATTLE].detect_match_select(frame):
            self.mode = GameMode.BATTLE
            return True
        if self.plugins[GameMode.SALMON].detect_match_select(frame):
            self.mode = GameMode.SALMON
            return True
        return False

    def extract_rate(self, frame: np.ndarray) -> int | None:
        plugin = self.plugins.get(self.mode)
        if plugin is None:
            return None
        return getattr(plugin, "extract_rate", lambda f: None)(frame)

    def detect_matching_start(self, frame: np.ndarray) -> bool:
        """マッチング開始画面を検出する。"""
        return self.registry.match("matching_start", frame)

    def detect_schedule_change(self, frame: np.ndarray) -> bool:
        return self.registry.match("schedule_change", frame)

    def detect_battle_start(self, frame: np.ndarray) -> bool:
        plugin = self.plugins.get(self.mode)
        if plugin is None:
            return False
        return plugin.detect_battle_start(frame)

    def detect_battle_abort(self, frame: np.ndarray) -> bool:
        plugin = self.plugins.get(self.mode)
        if plugin is None:
            return False
        return plugin.detect_battle_abort(frame)

    def detect_battle_finish(self, frame: np.ndarray) -> bool:
        plugin = self.plugins.get(self.mode)
        if plugin is None:
            return False
        return plugin.detect_battle_finish(frame)

    def detect_battle_finish_end(self, frame: np.ndarray) -> bool:
        plugin = self.plugins.get(self.mode)
        if plugin is None:
            return False
        return plugin.detect_battle_finish_end(frame)

    def detect_battle_judgement(self, frame: np.ndarray) -> bool:
        plugin = self.plugins.get(self.mode)
        if plugin is None:
            return False
        return plugin.detect_battle_judgement(frame)

    def extract_battle_judgement(self, frame: np.ndarray) -> str | None:
        """バトルの結果を抽出する。"""
        plugin = self.plugins.get(self.mode)
        if plugin is None:
            return None
        return plugin.extract_battle_judgement(frame)

    def detect_loading(self, frame: np.ndarray) -> bool:
        """ローディング画面かどうか判定する。"""
        return self.registry.match("loading", frame)

    def detect_loading_end(self, frame: np.ndarray) -> bool:
        """ローディング終了を検出する。"""
        return not self.detect_loading(frame)

    def detect_battle_result(self, frame: np.ndarray) -> bool:
        """結果画面を検出する。"""
        plugin = self.plugins.get(self.mode)
        if plugin is None:
            return False
        return plugin.detect_battle_result(frame)
