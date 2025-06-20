"""動画編集設定。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class VideoEditConfig:
    """動画編集に関する設定値。"""

    volume_multiplier: float = 1.0
