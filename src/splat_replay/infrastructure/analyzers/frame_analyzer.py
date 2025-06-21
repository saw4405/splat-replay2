"""ゲーム画面を解析するサービス。"""

from __future__ import annotations

import numpy as np

from splat_replay.infrastructure.analyzers.common.image_utils import (
    MatcherRegistry,
)

from splat_replay.shared.config import ImageMatchingSettings
from .plugin import AnalyzerPlugin

from splat_replay.shared.logger import get_logger

logger = get_logger()


class FrameAnalyzer:
    """OpenCV を用いた画面解析処理を提供する。"""

    def __init__(
        self, plugin: AnalyzerPlugin, settings: "ImageMatchingSettings"
    ) -> None:
        """プラグインと設定を受け取って初期化する。"""
        self.plugin = plugin
        self.registry = MatcherRegistry(settings)

    def detect_battle_start(self, frame: np.ndarray) -> bool:
        """バトル開始を検出する。"""
        return self.plugin.detect_battle_start(frame)

    def detect_loading(self, frame: np.ndarray) -> bool:
        """ローディング画面かどうか判定する。"""
        return self.plugin.detect_loading(frame)

    def detect_loading_end(self, frame: np.ndarray) -> bool:
        """ローディング終了を検出する。"""
        return self.plugin.detect_loading_end(frame)

    def detect_result(self, frame: np.ndarray) -> bool:
        """結果画面を検出する。"""
        return self.plugin.detect_result(frame)

    def detect_power_off(self, frame: np.ndarray) -> bool:
        """Switch の電源 OFF を検出する。"""
        return self.registry.match("power_off", frame)

    def detect_battle_finish(self, frame: np.ndarray) -> bool:
        """FINISH 表示を検出する。"""
        return self.registry.match("finish_display", frame)

    def detect_battle_stop(self, frame: np.ndarray) -> bool:
        """バトル終了画面を検出する。"""
        return self.registry.match("battle_finish", frame)
