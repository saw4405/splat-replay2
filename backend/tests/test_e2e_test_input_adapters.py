from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
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
from splat_replay.infrastructure.adapters.video.replay_recorder_controller import (
    ReplayRecorderController,
)
from splat_replay.infrastructure.filesystem import paths
from splat_replay.infrastructure.test_input import (
    resolve_replay_input_file_path,
    resolve_video_input_path,
)


class DummyLogger:
    def debug(self, *args: object, **kwargs: object) -> None:
        return None

    def info(self, *args: object, **kwargs: object) -> None:
        return None

    def warning(self, *args: object, **kwargs: object) -> None:
        return None

    def error(self, *args: object, **kwargs: object) -> None:
        return None


def _logger() -> DummyLogger:
    return DummyLogger()


def _write_test_video(path: Path, *, frames: int = 3) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(
        str(path),
        cv2.VideoWriter.fourcc(*"MJPG"),
        10.0,
        (64, 48),
    )
    if not writer.isOpened():
        raise RuntimeError(f"テスト動画を作成できませんでした: {path}")
    for index in range(frames):
        frame = np.full((48, 64, 3), fill_value=index * 40, dtype=np.uint8)
        writer.write(frame)
    writer.release()


def test_resolve_video_input_path_selects_smallest_mkv_from_directory(
    tmp_path: Path,
) -> None:
    video_dir = tmp_path / "recorded"
    video_dir.mkdir()
    (video_dir / "long_match.mkv").write_bytes(b"1234")
    (video_dir / "short_match.mkv").write_bytes(b"1")

    resolved = resolve_video_input_path(video_dir)

    assert resolved == (video_dir / "short_match.mkv").resolve()


def test_video_file_capture_reads_until_eof(tmp_path: Path) -> None:
    video_path = tmp_path / "input.avi"
    _write_test_video(video_path, frames=2)
    capture = VideoFileCapture(
        video_path,
        cast(BoundLogger, cast(Any, _logger())),
    )

    capture.setup()
    first_frame = capture.capture()
    second_frame = capture.capture()
    end_frame = capture.capture()

    assert first_frame is not None
    assert second_frame is not None
    assert end_frame is None
    assert capture.capture() is None

    capture.teardown()


@pytest.mark.asyncio
async def test_replay_recorder_controller_copies_input_and_emits_statuses(
    tmp_path: Path,
) -> None:
    input_video = tmp_path / "input.mkv"
    input_video.write_bytes(b"dummy-video")
    output_dir = tmp_path / "output"
    controller = ReplayRecorderController(
        input_video=input_video,
        output_dir=output_dir,
        logger=cast(BoundLogger, cast(Any, _logger())),
    )
    statuses: list[str] = []

    async def listener(status: str) -> None:
        statuses.append(status)

    controller.add_status_listener(listener)

    await controller.setup()
    await controller.start()
    await controller.pause()
    await controller.resume()
    output_video = await controller.stop()

    assert statuses == ["started", "paused", "resumed", "stopped"]
    assert output_video is not None
    assert output_video.exists()
    assert output_video.read_bytes() == input_video.read_bytes()


def test_adaptive_capture_device_checker_uses_video_file_mode(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    video_dir = tmp_path / "recorded"
    video_dir.mkdir()
    video_path = video_dir / "battle.mkv"
    video_path.write_bytes(b"video")
    settings_path = tmp_path / "settings.toml"
    monkeypatch.setattr(paths, "SETTINGS_FILE", settings_path)
    resolve_replay_input_file_path().write_text(
        (
            "{\n"
            f'  "video_path": "{str(video_dir).replace("\\", "\\\\")}"\n'
            "}\n"
        ),
        encoding="utf-8",
    )

    checker = AdaptiveCaptureDeviceChecker(
        SimpleNamespace(name="dummy-device"),
        cast(BoundLogger, cast(Any, _logger())),
    )

    assert checker.is_connected() is True
