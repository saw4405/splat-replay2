"""Capture adapters."""

from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = [
    "AdaptiveCapture",
    "AdaptiveCaptureDeviceChecker",
    "Capture",
    "CaptureDeviceChecker",
    "CaptureDeviceEnumerator",
    "NDICapture",
    "VideoFileCapture",
]

_LAZY_EXPORTS: dict[str, tuple[str, str]] = {
    "AdaptiveCapture": (".adaptive_capture", "AdaptiveCapture"),
    "AdaptiveCaptureDeviceChecker": (
        ".adaptive_capture_device_checker",
        "AdaptiveCaptureDeviceChecker",
    ),
    "Capture": (".capture", "Capture"),
    "CaptureDeviceChecker": (
        ".capture_device_checker",
        "CaptureDeviceChecker",
    ),
    "CaptureDeviceEnumerator": (
        ".capture_device_checker",
        "CaptureDeviceEnumerator",
    ),
    "NDICapture": (".ndi_capture", "NDICapture"),
    "VideoFileCapture": (".video_file_capture", "VideoFileCapture"),
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
