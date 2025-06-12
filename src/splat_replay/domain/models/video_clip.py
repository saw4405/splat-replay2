"""録画クリップ情報。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class VideoClip:
    """1 試合分の動画ファイルを表す。"""

    path: Path
    match_id: str | None = None
