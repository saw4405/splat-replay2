import asyncio
import io
import threading
from pathlib import Path
from subprocess import CompletedProcess
from typing import cast
from unittest.mock import MagicMock, patch

import pytest

from splat_replay.infrastructure.adapters.video.ffmpeg_processor import (
    FFmpegProcessor,
)


@pytest.mark.asyncio
async def test_ffmpeg_processor_run_with_progress_parsing() -> None:
    # logger mock
    logger = MagicMock()
    processor = FFmpegProcessor(logger)

    # コールバックのモック
    progress_calls: list[tuple[float, str | None]] = []

    def on_progress(percent: float, message: str | None) -> None:
        progress_calls.append((percent, message))

    # Popen のモック
    mock_process = MagicMock()

    # 模擬ログデータ (\r と \n を含む)
    log_data = (
        b"[concat] Opening 'recorded/clip1.mp4' for reading\r\n"
        b"frame= 100 fps=60 time=00:00:10.00 bitrate=100k\r"
        b"frame= 200 fps=60 time=00:00:20.50 bitrate=100k\r"
        b"[concat] Opening 'recorded/clip2.mp4' for reading\r\n"
        b"frame= 300 fps=60 time=00:00:30.000 bitrate=100k\r"
        b"frame= 305 fps=60 time=00:00:30.10 bitrate=100k\r"
    )

    mock_stderr = io.BytesIO(log_data)
    mock_process.stderr = mock_stderr
    mock_process.stdout = io.BytesIO(b"")
    mock_process.returncode = 0
    mock_process.communicate = MagicMock(return_value=(b"", b""))

    with patch("subprocess.Popen", return_value=mock_process):
        # 結合時間は総計 100 秒と仮定
        await processor._run_with_progress(
            command=["ffmpeg", "-dummy"],
            total_duration=100.0,
            on_progress=on_progress,
            cwd=Path("."),
        )

    # コールバックされた内容を検証
    assert len(progress_calls) > 0

    # パーセンテージ推移を確認
    # 10s -> 10%, 20.5s -> 20.5%, 30.0s -> 30%, 30.1s -> 30.1%
    # 頻度制御により、30.1% は 30% から 0.1% しか進んでいないため通知されないはず (0.5%しきい値)
    percents = [p[0] for p in progress_calls]
    messages = [p[1] for p in progress_calls]

    # 期待されるパーセント: [10.0, 20.5, 30.0]
    # (30.1 は 0.5 未満なのでスキップされるはず)
    assert 10.0 in percents
    assert 20.5 in percents
    assert 30.0 in percents
    assert 30.1 not in percents

    # クリップ名の追従を確認
    assert "結合中: clip1.mp4" in messages
    assert "結合中: clip2.mp4" in messages


@pytest.mark.asyncio
async def test_embed_metadata_and_thumbnail_uses_single_ffmpeg_command_with_progress(
    tmp_path: Path,
) -> None:
    logger = MagicMock()
    processor = FFmpegProcessor(logger)
    video = tmp_path / "clip.mkv"
    video.write_bytes(b"original")
    thumbnail = b"thumbnail-bytes"
    progress_calls: list[tuple[float, str | None]] = []
    command_calls: list[dict[str, object]] = []

    async def fake_get_video_length(path: Path) -> float:
        assert path == video
        return 123.0

    async def fake_run_with_progress(
        command: list[str],
        total_duration: float,
        on_progress,
        *,
        cwd: Path | None = None,
        input_bytes: bytes | None = None,
        progress_message: str = "動画を結合中",
        named_message_prefix: str | None = "結合中",
        cancel_check=None,
    ) -> CompletedProcess[str]:
        command_calls.append(
            {
                "command": command,
                "total_duration": total_duration,
                "cwd": cwd,
                "input_bytes": input_bytes,
                "progress_message": progress_message,
                "named_message_prefix": named_message_prefix,
                "cancel_check": cancel_check,
            }
        )
        video.with_name("temp.mkv").write_bytes(b"updated")
        on_progress(42.0, "埋め込み中")
        return CompletedProcess(command, 0, "", "")

    processor.get_video_length = fake_get_video_length  # type: ignore[method-assign]
    processor._run_with_progress = fake_run_with_progress  # type: ignore[method-assign]

    await processor.embed_metadata_and_thumbnail(
        video,
        {"title": "Test title", "description": "Test description"},
        thumbnail,
        on_progress=lambda percent, message: progress_calls.append(
            (percent, message)
        ),
    )

    assert video.read_bytes() == b"updated"
    assert len(command_calls) == 1
    call = command_calls[0]
    command = cast(list[str], call["command"])
    assert command.count("-i") == 2
    assert command.count("-metadata") == 2
    assert command[command.index("-metadata") + 1] == "title=Test title"
    assert "description=Test description" in command
    assert command[command.index("-c") + 1] == "copy"
    assert call["total_duration"] == 123.0
    assert call["input_bytes"] == thumbnail
    assert call["progress_message"] == "メタデータ・サムネイルを埋め込み中"
    assert call["named_message_prefix"] is None
    assert progress_calls == [
        (42.0, "埋め込み中"),
        (100.0, "メタデータ・サムネイルを埋め込み中"),
    ]


@pytest.mark.asyncio
async def test_embed_metadata_failure_keeps_original_video(
    tmp_path: Path,
) -> None:
    processor = FFmpegProcessor(MagicMock())
    video = tmp_path / "clip.mkv"
    video.write_bytes(b"original")
    temp = tmp_path / "temp.mkv"

    async def fail_ffmpeg(
        *args: object, **kwargs: object
    ) -> CompletedProcess[str]:
        _ = args, kwargs
        temp.write_bytes(b"partial")
        return CompletedProcess(["ffmpeg"], 1, "", "failed")

    processor._run_text = fail_ffmpeg  # type: ignore[method-assign]

    with pytest.raises(RuntimeError, match="FFmpeg終了コード 1"):
        await processor.embed_metadata(video, {"title": "test"})

    assert video.read_bytes() == b"original"
    assert not temp.exists()


@pytest.mark.asyncio
async def test_windows_ffmpeg_process_is_terminated_on_cancel() -> None:
    processor = FFmpegProcessor(MagicMock())
    cancel_requested = False
    terminated = threading.Event()

    class _Process:
        returncode: int | None = None

        def poll(self) -> int | None:
            return self.returncode

        def terminate(self) -> None:
            self.returncode = -15
            terminated.set()

        def kill(self) -> None:
            self.returncode = -9
            terminated.set()

        def wait(self, timeout: float | None = None) -> int:
            _ = timeout
            assert self.returncode is not None
            return self.returncode

        def communicate(
            self,
            input: bytes | None = None,
            timeout: float | None = None,
        ) -> tuple[bytes, bytes]:
            nonlocal cancel_requested
            _ = input, timeout
            cancel_requested = True
            assert terminated.wait(timeout=1.0)
            return b"", b"cancelled"

    process = _Process()
    with patch("subprocess.Popen", return_value=process):
        with pytest.raises(asyncio.CancelledError):
            await processor._run_text_windows(
                ["ffmpeg", "-version"],
                cancel_check=lambda: cancel_requested,
            )

    assert process.returncode == -15
