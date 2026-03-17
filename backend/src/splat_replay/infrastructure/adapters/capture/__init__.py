"""Capture adapters."""

from __future__ import annotations

from splat_replay.infrastructure.adapters.capture.adaptive_capture import (
    AdaptiveCapture,
)
from splat_replay.infrastructure.adapters.capture.adaptive_capture_device_checker import (
    AdaptiveCaptureDeviceChecker,
)
from splat_replay.infrastructure.adapters.capture.capture import Capture
from splat_replay.infrastructure.adapters.capture.capture_device_checker import (
    CaptureDeviceChecker,
    CaptureDeviceEnumerator,
)
from splat_replay.infrastructure.adapters.capture.ndi_capture import NDICapture
from splat_replay.infrastructure.adapters.capture.video_file_capture import (
    VideoFileCapture,
)

__all__ = [
    "AdaptiveCapture",
    "AdaptiveCaptureDeviceChecker",
    "Capture",
    "CaptureDeviceChecker",
    "CaptureDeviceEnumerator",
    "NDICapture",
    "VideoFileCapture",
]
