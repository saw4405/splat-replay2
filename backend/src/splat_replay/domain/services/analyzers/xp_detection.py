from __future__ import annotations

from dataclasses import dataclass
import re

from splat_replay.domain.models import Frame, XP

XP_OCR_INVALID_FORMAT = "XP_OCR_INVALID_FORMAT"
XP_OCR_PARSE_FAILED = "XP_OCR_PARSE_FAILED"
XP_OCR_TEXT_PATTERN = re.compile(r"^\d{3,4}\.\d$")


def parse_xp_ocr_text(ocr_text: str) -> tuple[float | None, str | None]:
    stripped = ocr_text.strip()
    if not XP_OCR_TEXT_PATTERN.fullmatch(stripped):
        return None, XP_OCR_INVALID_FORMAT
    try:
        return float(stripped), None
    except ValueError:
        return None, XP_OCR_PARSE_FAILED


@dataclass(frozen=True)
class XPExtractionDiagnostics:
    """XP OCR の1回分の抽出結果と診断用画像。"""

    xp_roi: Frame
    xp_processed: Frame
    ocr_text: str | None
    parsed_xp: float | None
    xp: XP | None
    validation_error: str | None
