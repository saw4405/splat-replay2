"""YouTube アップロード設定。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence


@dataclass
class YouTubeUploadConfig:
    """YouTube へアップロードするための設定値。"""

    upload_privacy: str = "private"
    title_template: str = (
        "{BATTLE}({RATE}) {RULE} {WIN}勝{LOSE}敗 {DAY} {SCHEDULE}時～"
    )
    description_template: str = "{CHAPTERS}"
    chapter_template: str = "{RESULT} {KILL}k {DEATH}d {SPECIAL}s  {STAGE}"
    tags: Sequence[str] = field(default_factory=lambda: ["Splatoon3"])
    playlist_id: str = ""
