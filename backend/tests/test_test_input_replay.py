from __future__ import annotations

import os
from pathlib import Path
from typing import Any, cast

import cv2
import numpy as np
import pytest
from structlog.stdlib import BoundLogger

from splat_replay.infrastructure.adapters.capture.adaptive_capture_device_checker import (
    AdaptiveCaptureDeviceChecker,
)
from splat_replay.infrastructure.adapters.capture.video_file_capture import (
    VideoFileCapture,
)
from splat_replay.infrastructure.adapters.storage.settings_repository import (
    TomlSettingsRepository,
)
from splat_replay.infrastructure.adapters.video.replay_recorder_controller import (
    ReplayRecorderController,
)
from splat_replay.infrastructure.config import (
    load_settings_from_toml,
    save_settings_to_toml,
)
from splat_replay.infrastructure.filesystem import paths
from splat_replay.infrastructure.test_input import (
    normalize_input_path,
    resolve_replay_input_file_path,
    resolve_video_input_path,
)


class DummyLogger:
    def debug(self, *args, **kwargs) -> None:
        return None

    def info(self, *args, **kwargs) -> None:
        return None

    def warning(self, *args, **kwargs) -> None:
        return None

    def error(self, *args, **kwargs) -> None:
        return None


def _write_dummy_video(
    path: Path,
    *,
    frame_count: int = 2,
    width: int = 32,
    height: int = 24,
) -> None:
    writer = cv2.VideoWriter(
        str(path),
        cv2.VideoWriter.fourcc(*"mp4v"),
        5.0,
        (width, height),
    )
    assert writer.isOpened(), f"VideoWriter を開けません: {path}"
    for index in range(frame_count):
        frame = np.full((height, width, 3), index * 60, dtype=np.uint8)
        writer.write(frame)
    writer.release()


def _write_replay_input(
    *,
    replay_input_path: Path,
    video_path: str,
) -> None:
    replay_input_path.write_text(
        (f'{{\n  "video_path": "{video_path.replace("\\", "\\\\")}"\n}}\n'),
        encoding="utf-8",
    )


def test_normalize_input_path_converts_windows_path() -> None:
    expected = (
        Path(r"C:\Users\shogo\Downloads\videos\recorded")
        if os.name == "nt"
        else Path("/mnt/c/Users/shogo/Downloads/videos/recorded")
    )
    assert (
        normalize_input_path(r"C:\Users\shogo\Downloads\videos\recorded")
        == expected
    )


def test_resolve_video_input_path_picks_smallest_mkv_in_directory(
    tmp_path: Path,
) -> None:
    later = tmp_path / "b_video.mkv"
    earlier = tmp_path / "a_video.mkv"
    later.write_bytes(b"later")
    earlier.write_bytes(b"earlier")

    resolved = resolve_video_input_path(tmp_path)

    assert resolved == later.resolve()


def test_video_file_capture_returns_none_after_eof(tmp_path: Path) -> None:
    video_path = tmp_path / "sample.mp4"
    _write_dummy_video(video_path, frame_count=2)

    capture = VideoFileCapture(
        video_path,
        cast(BoundLogger, cast(Any, DummyLogger())),
    )
    capture.setup()

    first = capture.capture()
    first_time = capture.current_time_seconds()
    second = capture.capture()
    second_time = capture.current_time_seconds()
    third = capture.capture()
    fourth = capture.capture()

    capture.teardown()

    assert first is not None
    assert second is not None
    assert first_time is not None
    assert second_time is not None
    assert second_time > first_time
    assert third is None
    assert fourth is None


@pytest.mark.asyncio
async def test_replay_recorder_controller_copies_input_video_and_emits_statuses(
    tmp_path: Path,
) -> None:
    input_video = tmp_path / "input.mp4"
    _write_dummy_video(input_video, frame_count=3)
    output_dir = tmp_path / "out"
    recorder = ReplayRecorderController(
        input_video,
        output_dir,
        cast(BoundLogger, cast(Any, DummyLogger())),
    )
    statuses: list[str] = []

    async def listener(status: str) -> None:
        statuses.append(status)

    recorder.add_status_listener(listener)

    await recorder.setup()
    await recorder.start()
    await recorder.pause()
    await recorder.resume()
    output = await recorder.stop()

    assert output is not None
    assert output.exists()
    assert output.read_bytes() == input_video.read_bytes()
    assert statuses == ["started", "paused", "resumed", "stopped"]


def test_adaptive_capture_device_checker_uses_replay_input_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings_path = tmp_path / "settings.toml"
    video_path = tmp_path / "sample.mp4"
    _write_dummy_video(video_path)
    monkeypatch.setattr(paths, "SETTINGS_FILE", settings_path)
    _write_replay_input(
        replay_input_path=resolve_replay_input_file_path(),
        video_path=str(video_path),
    )

    settings = load_settings_from_toml(settings_path)
    checker = AdaptiveCaptureDeviceChecker(
        settings.capture_device,
        cast(BoundLogger, cast(Any, DummyLogger())),
    )

    assert checker.is_connected() is True


def test_settings_repository_does_not_expose_e2e_replay_input(
    tmp_path: Path,
) -> None:
    settings_path = tmp_path / "settings.toml"
    repository = TomlSettingsRepository(settings_path=settings_path)

    sections = repository.fetch_sections()
    assert "test_input" not in [section["id"] for section in sections]


def test_save_settings_to_toml_does_not_write_test_input_section(
    tmp_path: Path,
) -> None:
    settings_path = tmp_path / "settings.toml"
    settings = load_settings_from_toml(settings_path, create_if_missing=False)

    save_settings_to_toml(settings, settings_path)

    saved_text = settings_path.read_text(encoding="utf-8")
    assert "[test_input]" not in saved_text
