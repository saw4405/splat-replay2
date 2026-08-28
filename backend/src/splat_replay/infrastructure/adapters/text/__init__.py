"""Text processing adapters."""

from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = [
    "ReplayOCRAdapter",
    "SubtitleEditor",
    "TesseractOCR",
]

_LAZY_EXPORTS: dict[str, tuple[str, str]] = {
    "ReplayOCRAdapter": (".replay_ocr", "ReplayOCRAdapter"),
    "SubtitleEditor": (".subtitle_editor", "SubtitleEditor"),
    "TesseractOCR": (".tesseract_ocr", "TesseractOCR"),
}


def __getattr__(name: str) -> Any:
    if name not in _LAZY_EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    module_name, attr_name = _LAZY_EXPORTS[name]
    value = getattr(import_module(module_name, __name__), attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(__all__)
