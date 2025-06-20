"""スプラトゥーンバトル解析器。"""

from __future__ import annotations

from pathlib import Path


class SplatoonBattleAnalyzer:
    """バトル開始や結果を解析する。"""

    def analyze(self, frame: Path) -> None:
        """フレームを解析する。"""
        raise NotImplementedError
