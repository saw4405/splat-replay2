"""サムネイルのルール名画像を検証するポート。"""

from pathlib import Path
from typing import Protocol


class ThumbnailRuleImageResolverPort(Protocol):
    """利用可能な白文字・透明PNGを返す。欠損・不正画像は None。"""

    def resolve(self, preferred_path: Path) -> Path | None: ...
