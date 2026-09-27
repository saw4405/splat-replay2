from __future__ import annotations

import subprocess
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from structlog.stdlib import BoundLogger

from splat_replay.infrastructure.adapters.capture import capture_device_checker


def test_connected_device_is_found_by_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = "\n".join(
        [
            '[dshow] "MiraBox Capture" (video)',
            '[dshow] Alternative name "@device_pnp_old"',
            '[dshow] "Digital Audio Interface" (audio)',
        ]
    )
    monkeypatch.setattr(capture_device_checker.sys, "platform", "win32")
    monkeypatch.setattr(
        capture_device_checker.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess([], 1, "", output),
    )
    settings = SimpleNamespace(name="MiraBox Capture")
    checker = capture_device_checker.CaptureDeviceChecker(
        settings, Mock(spec=BoundLogger)
    )

    assert checker.is_connected() is True
    assert capture_device_checker._get_video_devices_from_ffmpeg(
        Mock(spec=BoundLogger)
    ) == ["MiraBox Capture"]
