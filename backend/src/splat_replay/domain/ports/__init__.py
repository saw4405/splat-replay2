"""Domain ports - interfaces for external dependencies."""

from __future__ import annotations

from splat_replay.domain.ports.image_editor import (
    ImageEditorFactory,
    ImageEditorPort,
)
from splat_replay.domain.ports.image_matcher import ImageMatcherPort
from splat_replay.domain.ports.ocr import OCRPort

__all__ = [
    "ImageEditorFactory",
    "ImageEditorPort",
    "ImageMatcherPort",
    "OCRPort",
]
