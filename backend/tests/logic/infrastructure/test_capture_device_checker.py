from __future__ import annotations

import subprocess
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from structlog.stdlib import BoundLogger

from splat_replay.infrastructure.adapters.capture import capture_device_checker

_AVFOUNDATION_OUTPUT = "\n".join(
    [
        "[AVFoundation indev @ 0x1] AVFoundation video devices:",
        "[AVFoundation indev @ 0x1] [0] MiraBox Capture",
        "[AVFoundation indev @ 0x1] [1] Capture screen 0",
        "[AVFoundation indev @ 0x1] [2] MiraBox Capture",
        "[AVFoundation indev @ 0x1] AVFoundation audio devices:",
        "[AVFoundation indev @ 0x1] [0] USB Audio Interface",
    ]
)


def _stub_ffmpeg(
    monkeypatch: pytest.MonkeyPatch,
    stderr: str,
    *,
    return_code: int = 1,
) -> Mock:
    completed = subprocess.CompletedProcess([], return_code, "", stderr)
    ffmpeg_run = Mock(return_value=completed)
    monkeypatch.setattr(capture_device_checker.sys, "platform", "darwin")
    monkeypatch.setattr(capture_device_checker.subprocess, "run", ffmpeg_run)
    return ffmpeg_run


def test_macos_lists_video_names_only_and_uses_avfoundation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ffmpeg_run = _stub_ffmpeg(monkeypatch, _AVFOUNDATION_OUTPUT)
    enumerator = capture_device_checker.CaptureDeviceEnumerator(
        Mock(spec=BoundLogger)
    )

    assert enumerator.list_video_devices() == ["MiraBox Capture"]
    ffmpeg_run.assert_called_once_with(
        ["ffmpeg", "-f", "avfoundation", "-list_devices", "true", "-i", ""],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=10.0,
        creationflags=0,
    )


def test_macos_connection_uses_current_display_name_even_when_duplicated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_ffmpeg(monkeypatch, _AVFOUNDATION_OUTPUT)
    checker = capture_device_checker.CaptureDeviceChecker(
        SimpleNamespace(name="MiraBox Capture"), Mock(spec=BoundLogger)
    )

    assert checker.is_connected() is True


def test_macos_connection_is_false_when_only_another_device_is_listed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = _AVFOUNDATION_OUTPUT.replace("MiraBox Capture", "Elgato Capture")
    _stub_ffmpeg(monkeypatch, output)
    checker = capture_device_checker.CaptureDeviceChecker(
        SimpleNamespace(name="MiraBox Capture"), Mock(spec=BoundLogger)
    )

    assert checker.is_connected() is False


def test_macos_unselected_device_is_not_connected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ffmpeg_run = _stub_ffmpeg(monkeypatch, _AVFOUNDATION_OUTPUT)
    checker = capture_device_checker.CaptureDeviceChecker(
        SimpleNamespace(name=""), Mock(spec=BoundLogger)
    )

    assert checker.is_connected() is False
    ffmpeg_run.assert_not_called()


@pytest.mark.parametrize(
    "stderr",
    [
        "Unknown input format: 'avfoundation'",
        "[AVFoundation indev @ 0x1] AVFoundation video devices:\n"
        "[AVFoundation indev @ 0x1] [0] Capture screen 0\n"
        "[AVFoundation indev @ 0x1] AVFoundation audio devices:",
        "[AVFoundation indev @ 0x1] AVFoundation video devices:\n"
        "[AVFoundation indev @ 0x1] [0] MiraBox Capture\n"
        "[AVFoundation indev @ 0x1] AVFoundation audio devices:\n"
        "[AVFoundation indev @ 0x1] Video permission denied",
    ],
)
def test_macos_returns_empty_for_failed_permission_or_no_hardware_listing(
    monkeypatch: pytest.MonkeyPatch,
    stderr: str,
) -> None:
    _stub_ffmpeg(monkeypatch, stderr)
    enumerator = capture_device_checker.CaptureDeviceEnumerator(
        Mock(spec=BoundLogger)
    )
    checker = capture_device_checker.CaptureDeviceChecker(
        SimpleNamespace(name="MiraBox Capture"), Mock(spec=BoundLogger)
    )

    assert enumerator.list_video_devices() == []
    assert checker.is_connected() is False


@pytest.mark.parametrize(
    "error",
    [
        FileNotFoundError("ffmpeg not found"),
        subprocess.TimeoutExpired("ffmpeg", timeout=10.0),
    ],
)
def test_macos_returns_empty_when_ffmpeg_is_unavailable_or_times_out(
    monkeypatch: pytest.MonkeyPatch,
    error: Exception,
) -> None:
    ffmpeg_run = Mock(side_effect=error)
    monkeypatch.setattr(capture_device_checker.sys, "platform", "darwin")
    monkeypatch.setattr(capture_device_checker.subprocess, "run", ffmpeg_run)
    enumerator = capture_device_checker.CaptureDeviceEnumerator(
        Mock(spec=BoundLogger)
    )
    checker = capture_device_checker.CaptureDeviceChecker(
        SimpleNamespace(name="MiraBox Capture"), Mock(spec=BoundLogger)
    )

    assert enumerator.list_video_devices() == []
    assert checker.is_connected() is False


def test_windows_directshow_enumeration_is_preserved(
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
    assert capture_device_checker.CaptureDeviceEnumerator(
        Mock(spec=BoundLogger)
    ).list_video_devices() == ["MiraBox Capture"]
