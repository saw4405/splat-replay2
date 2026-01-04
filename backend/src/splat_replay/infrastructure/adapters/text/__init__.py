"""Text processing adapters."""

from __future__ import annotations

from splat_replay.infrastructure.adapters.text.subtitle_editor import (
    SubtitleEditor,
)
from splat_replay.infrastructure.adapters.text.tesseract_ocr import (
    TesseractOCR,
)

__all__ = [
    "SubtitleEditor",
    "TesseractOCR",
]
