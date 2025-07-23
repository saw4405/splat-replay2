"""Image matcher port definition."""

from __future__ import annotations

from typing import Protocol

from splat_replay.domain.models import Frame


class ImageMatcherPort(Protocol):
    """画像処理の技術的機能を提供するポート。"""

    def match(self, key: str, image: Frame) -> bool: ...

    def matched_name(self, group: str, image: Frame) -> str | None: ...
