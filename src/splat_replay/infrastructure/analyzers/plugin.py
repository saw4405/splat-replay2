from __future__ import annotations

"""解析プラグイン共通インターフェース。"""

from typing import Protocol
import numpy as np


class AnalyzerPlugin(Protocol):
    """ゲーム画面解析プラグインのプロトコル。"""

    def detect_battle_start(self, frame: np.ndarray) -> bool:
        """バトル開始を検出する。"""

    def detect_loading(self, frame: np.ndarray) -> bool:
        """ローディング画面か判定する。"""

    def detect_loading_end(self, frame: np.ndarray) -> bool:
        """ローディング終了を検出する。"""

    def detect_result(self, frame: np.ndarray) -> bool:
        """結果画面を検出する。"""
