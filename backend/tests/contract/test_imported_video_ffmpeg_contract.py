"""持込動画の区間出力が標準的なMP4として再生できる契約。"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from subprocess import CompletedProcess
from typing import TypedDict, cast
from unittest.mock import MagicMock

import pytest
from PIL import Image
import io

from splat_replay.infrastructure.adapters.video.ffmpeg_processor import (
    FFmpegProcessor,
)

pytestmark = pytest.mark.contract


class _FFprobeStream(TypedDict, total=False):
    codec_type: str
    codec_name: str
    pix_fmt: str


class _FFprobeFormat(TypedDict, total=False):
    duration: str


class _FFprobeResult(TypedDict):
    streams: list[_FFprobeStream]
    format: _FFprobeFormat


def _require_binary(name: str) -> str:
    binary = shutil.which(name)
    if binary is None:
        pytest.skip(f"imported-video contract requires {name} on PATH")
    assert binary is not None
    return binary


def _make_source(ffmpeg: str, path: Path, with_audio: bool) -> None:
    command = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "lavfi",
        "-i",
        "color=c=red:s=64x64:r=25:d=1",
        "-f",
        "lavfi",
        "-i",
        "color=c=green:s=64x64:r=25:d=1",
        "-f",
        "lavfi",
        "-i",
        "color=c=blue:s=64x64:r=25:d=1",
    ]
    if with_audio:
        command.extend(
            [
                "-f",
                "lavfi",
                "-i",
                "sine=frequency=440:sample_rate=44100:duration=3",
            ]
        )
    command.extend(
        [
            "-filter_complex",
            "[0:v][1:v][2:v]concat=n=3:v=1:a=0[v]",
            "-map",
            "[v]",
        ]
    )
    if with_audio:
        command.extend(["-map", "3:a:0", "-shortest"])
    command.extend(
        [
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-pix_fmt",
            "yuv420p",
        ]
    )
    if with_audio:
        command.extend(["-c:a", "aac"])
    command.append(str(path))
    subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )


def _probe(ffprobe: str, path: Path) -> _FFprobeResult:
    result = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration:stream=codec_type,codec_name,pix_fmt",
            "-of",
            "json",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=15,
    )
    return cast(_FFprobeResult, json.loads(result.stdout))


@pytest.mark.asyncio
@pytest.mark.parametrize("with_audio", [False, True])
async def test_cut_and_concat_preserve_precise_boundary_and_optional_audio(
    tmp_path: Path, with_audio: bool
) -> None:
    ffmpeg = _require_binary("ffmpeg")
    ffprobe = _require_binary("ffprobe")
    source = tmp_path / "source.mp4"
    first = tmp_path / "clips" / "first.mp4"
    second = tmp_path / "clips" / "second.mp4"
    output = tmp_path / "output.mp4"
    first.parent.mkdir()
    _make_source(ffmpeg, source, with_audio)
    processor = FFmpegProcessor(MagicMock())

    await processor.cut_segment(source, 1.08, 1.84, first)
    await processor.cut_segment(source, 2.08, 2.84, second)
    await processor.merge([first, second], output)

    probe = _probe(ffprobe, output)
    streams = probe["streams"]
    assert isinstance(streams, list)
    video = next(
        stream for stream in streams if stream["codec_type"] == "video"
    )
    assert video["codec_name"] == "h264"
    assert video["pix_fmt"] == "yuv420p"
    assert (
        any(stream["codec_type"] == "audio" for stream in streams)
        is with_audio
    )
    duration_value = probe["format"].get("duration")
    assert duration_value is not None
    duration = float(duration_value)
    assert 1.3 <= duration <= 1.7

    # 1.08秒開始点は緑区間にあり、先行赤区間のkeyframeへずれない。
    frame = await processor.extract_frame(first, 0.12)
    assert frame is not None
    pixel = Image.open(io.BytesIO(frame)).convert("RGB").getpixel((32, 32))
    assert isinstance(pixel, tuple) and len(pixel) == 3
    red, green, blue = pixel
    assert green > red and green > blue

    info = await processor.inspect_imported_video(output)
    assert info.has_video is True
    assert info.has_audio is with_audio


@pytest.mark.asyncio
async def test_probe_rejects_playlist_formats_and_limits_input_protocols(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    processor = FFmpegProcessor(MagicMock())
    commands: list[list[str]] = []

    async def fake_run_text(
        command: list[str], **kwargs: object
    ) -> CompletedProcess[str]:
        commands.append(command)
        return CompletedProcess(
            command,
            0,
            json.dumps(
                {
                    "format": {"duration": "30", "format_name": "hls"},
                    "streams": [{"codec_type": "video"}],
                }
            ),
            "",
        )

    monkeypatch.setattr(processor, "_run_text", fake_run_text)
    with pytest.raises(ValueError, match="対応していない動画形式"):
        await processor.inspect_imported_video(tmp_path / "playlist.mp4")

    command = commands[0]
    assert command[command.index("-protocol_whitelist") + 1] == "file,pipe"
    assert (
        command[command.index("-format_whitelist") + 1] == "mov,matroska,avi"
    )
    assert "-i" in command
