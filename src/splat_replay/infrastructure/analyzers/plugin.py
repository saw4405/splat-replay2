from __future__ import annotations

"""解析プラグイン共通インターフェース。"""

from typing import Protocol
import numpy as np


class AnalyzerPlugin(Protocol):
    """ゲーム画面解析プラグインのプロトコル。"""

    def detect_match_select(self, frame: np.ndarray) -> bool:
        """マッチ選択画面か判定する。"""

    def extract_rate(self, frame: np.ndarray) -> int | None:
        """レート数値を取得する。"""

    def detect_matching_start(self, frame: np.ndarray) -> bool:
        """マッチング開始を検出する。"""

    def detect_schedule_change(self, frame: np.ndarray) -> bool:
        """スケジュール変更を検出する。"""

    def detect_battle_start(self, frame: np.ndarray) -> bool:
        """バトル開始を検出する。"""

    def detect_battle_abort(self, frame: np.ndarray) -> bool:
        """バトル中断を検出する。"""

    def detect_loading(self, frame: np.ndarray) -> bool:
        """ローディング画面か判定する。"""

    def detect_loading_end(self, frame: np.ndarray) -> bool:
        """ローディング終了を検出する。"""

    def detect_battle_finish(self, frame: np.ndarray) -> bool:
        """Finish 演出を検出する。"""

    def detect_battle_finish_end(self, frame: np.ndarray) -> bool:
        """Finish 終了を検出する。"""

    def detect_battle_judgement(self, frame: np.ndarray) -> str | None:
        """勝敗画面から勝敗を取得する。"""

    def detect_battle_result(self, frame: np.ndarray) -> bool:
        """結果画面を検出する。"""
