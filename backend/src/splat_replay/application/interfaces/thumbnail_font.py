"""サムネイル用フォント解決ポート。"""

from pathlib import Path
from typing import Protocol


class ThumbnailFontResolverPort(Protocol):
    """優先フォントまたは OS の日本語フォントを解決する。"""

    def resolve(self, preferred_path: Path) -> Path | None: ...
