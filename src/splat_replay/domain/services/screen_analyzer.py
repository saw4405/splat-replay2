"""画面解析サービス。"""

from __future__ import annotations

from pathlib import Path


class ScreenAnalyzer:
    """OpenCV などを利用した画面解析処理を提供する。"""

    def detect_battle_start(self, frame: Path) -> bool:
        """バトル開始を検出する。"""
        raise NotImplementedError

    def detect_loading(self, frame: Path) -> bool:
        """ローディング画面かどうか判定する。"""
        raise NotImplementedError

    def detect_loading_end(self, frame: Path) -> bool:
        """ローディング終了を検出する。"""
        raise NotImplementedError

    def detect_result(self, frame: Path) -> bool:
        """結果画面を検出する。"""
        raise NotImplementedError

    def detect_power_off(self) -> bool:
        """Switch の電源 OFF を検出する。"""
        raise NotImplementedError
