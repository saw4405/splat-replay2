"""動画クリップを表すデータクラス。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class VideoClip:
    """録画ファイル1本を表す。"""

    path: Path
    match_id: str
