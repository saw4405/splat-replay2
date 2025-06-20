"""サーモンラン解析器。"""

from __future__ import annotations

from pathlib import Path


class SplatoonSalmonAnalyzer:
    """サーモンラン用の解析器。"""

    def analyze(self, frame: Path) -> None:
        """フレームを解析する。"""
        raise NotImplementedError
