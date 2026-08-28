"""replay 入力の観測を返す OCR アダプタ。"""

from __future__ import annotations

from typing import Optional

from splat_replay.domain.models import Frame
from splat_replay.domain.ports import OCRPort, OCRPurpose
from splat_replay.infrastructure.test_input import resolve_replay_ocr_text


class ReplayOCRAdapter(OCRPort):
    """fixture 由来の OCR 観測を既存 OCR ポートとして返す。"""

    async def recognize_text(
        self,
        image: Frame,
        ps_mode: Optional[str] = None,
        whitelist: Optional[str] = None,
        purpose: OCRPurpose | None = None,
    ) -> str | None:
        """用途に対応する観測値を返し、暗黙の実 OCR へ戻らない。"""
        del image, ps_mode, whitelist
        if purpose is None:
            raise RuntimeError("replay OCR には purpose が必要です")
        return resolve_replay_ocr_text(purpose)
