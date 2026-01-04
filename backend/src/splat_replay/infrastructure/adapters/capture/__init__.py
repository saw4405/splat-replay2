"""Capture adapters."""

from __future__ import annotations

from splat_replay.infrastructure.adapters.capture.capture import Capture
from splat_replay.infrastructure.adapters.capture.capture_device_checker import (
    CaptureDeviceChecker,
    CaptureDeviceEnumerator,
)
from splat_replay.infrastructure.adapters.capture.ndi_capture import NDICapture

__all__ = [
    "Capture",
    "CaptureDeviceChecker",
    "CaptureDeviceEnumerator",
    "NDICapture",
]
