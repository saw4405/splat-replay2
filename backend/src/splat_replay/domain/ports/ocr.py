from __future__ import annotations

from typing import Optional, Protocol

from splat_replay.domain.models import Frame


class OCRPort(Protocol):
    """OCR処理を提供するポート。"""

    async def recognize_text(
        self,
        image: Frame,
        ps_mode: Optional[str] = None,
        whitelist: Optional[str] = None,
    ) -> Optional[str]: ...
