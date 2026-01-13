"""FFmpeg adapter utilities."""

from __future__ import annotations

import asyncio
import contextlib
import json
import subprocess
from asyncio import subprocess as asyncio_subprocess
from pathlib import Path
from subprocess import CompletedProcess
from typing import Dict, List, Literal, Optional, Sequence, TypeVar

from structlog.stdlib import BoundLogger

from splat_replay.application.interfaces import VideoEditorPort

ResultT = TypeVar("ResultT", str, bytes)


class FFmpegProcessor(VideoEditorPort):
    """Provides high-level helpers around ffmpeg/ffprobe commands."""

    def __init__(self, logger: BoundLogger) -> None:
        self.logger = logger
        # 動画長のキャッシュ (GUI リスト表示時の ffprobe 過多を防止)
        self._length_cache: dict[Path, float | None] = {}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    async def _run_text(
        self,
        command: Sequence[str],
        *,
        cwd: Path | None = None,
        input_text: str | None = None,
        timeout: float | None = None,
    ) -> CompletedProcess[str]:
        # Windows環境での asyncio.create_subprocess_exec の NotImplementedError 回避
        # subprocess.run を asyncio.to_thread でラップして実行
        import sys

        if sys.platform == "win32":
            return await self._run_text_windows(
                command, cwd=cwd, input_text=input_text, timeout=timeout
            )

        process = await asyncio.create_subprocess_exec(
            *command,
            cwd=str(cwd) if cwd else None,
            stdin=asyncio_subprocess.PIPE if input_text is not None else None,
            stdout=asyncio_subprocess.PIPE,
            stderr=asyncio_subprocess.PIPE,
        )
        input_bytes = (
            input_text.encode("utf-8") if input_text is not None else None
        )
        try:
            if timeout is None:
                stdout_bytes, stderr_bytes = await process.communicate(
                    input_bytes
                )
            else:
                try:
                    stdout_bytes, stderr_bytes = await asyncio.wait_for(
                        process.communicate(input_bytes), timeout=timeout
                    )
                except asyncio.TimeoutError as exc:
                    process.kill()
                    with contextlib.suppress(Exception):
                        await process.communicate()
                    raise subprocess.TimeoutExpired(
                        list(command), timeout
                    ) from exc
        except asyncio.CancelledError:
            process.kill()
            with contextlib.suppress(Exception):
                await process.communicate()
            raise
        return CompletedProcess(
            args=list(command),
            returncode=process.returncode
            if process.returncode is not None
            else -1,
            stdout=stdout_bytes.decode("utf-8", errors="replace"),
            stderr=stderr_bytes.decode("utf-8", errors="replace"),
        )

    async def _run_text_windows(
        self,
        command: Sequence[str],
        *,
        cwd: Path | None = None,
        input_text: str | None = None,
        timeout: float | None = None,
    ) -> CompletedProcess[str]:
        """Windows環境での subprocess 実行（asyncio.to_thread を使用）。"""

        def run_subprocess() -> CompletedProcess[str]:
            input_bytes = (
                input_text.encode("utf-8") if input_text is not None else None
            )
            result = subprocess.run(
                command,
                cwd=str(cwd) if cwd else None,
                input=input_bytes,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout,
            )
            return CompletedProcess(
                args=list(command),
                returncode=result.returncode,
                stdout=result.stdout.decode("utf-8", errors="replace"),
                stderr=result.stderr.decode("utf-8", errors="replace"),
            )

        return await asyncio.to_thread(run_subprocess)

    async def _run_binary(
        self,
        command: Sequence[str],
        *,
        input_bytes: bytes | None = None,
    ) -> CompletedProcess[bytes]:
        process = await asyncio.create_subprocess_exec(
            *command,
            stdin=asyncio_subprocess.PIPE if input_bytes is not None else None,
            stdout=asyncio_subprocess.PIPE,
            stderr=asyncio_subprocess.PIPE,
        )
        try:
            stdout_bytes, stderr_bytes = await process.communicate(input_bytes)
        except asyncio.CancelledError:
            process.kill()
            with contextlib.suppress(Exception):
                await process.communicate()
            raise
        return CompletedProcess(
            args=list(command),
            returncode=process.returncode
            if process.returncode is not None
            else -1,
            stdout=stdout_bytes,
            stderr=stderr_bytes,
        )

    def _log_failure(
        self,
        message: str,
        result: CompletedProcess[ResultT],
    ) -> None:
        stderr_raw = result.stderr
        if isinstance(stderr_raw, bytes):
            stderr = stderr_raw.decode("utf-8", errors="ignore")
        else:
            stderr = stderr_raw or ""
        stdout_raw = result.stdout
        if isinstance(stdout_raw, bytes):
            stdout = stdout_raw.decode("utf-8", errors="ignore")
        else:
            stdout = stdout_raw or ""
        self.logger.error(message, error=stderr, output=stdout)

    # ------------------------------------------------------------------
    # VideoEditorPort implementation
    # ------------------------------------------------------------------
    async def merge(self, clips: list[Path], output: Path) -> Path:
        abs_clips = [clip.resolve() for clip in clips]
        self.logger.info(
            "FFmpeg: クリップ結合", clips=[str(c) for c in abs_clips]
        )
        if not abs_clips:
            raise ValueError("clips is empty")

        filelist = abs_clips[0].parent / "concat.txt"
        filelist.write_text(
            "\n".join(f"file '{clip}'" for clip in abs_clips),
            encoding="utf-8",
        )

        result = await self._run_text(
            [
                "ffmpeg",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(filelist),
                "-c",
                "copy",
                str(output.resolve()),
            ],
            cwd=abs_clips[0].parent,
        )
        filelist.unlink(missing_ok=True)
        if result.returncode != 0:
            self._log_failure("FFmpeg: 結合に失敗", result)
        return output

    async def embed_metadata(
        self, path: Path, metadata: Dict[str, str]
    ) -> None:
        abs_path = path.resolve()
        self.logger.info(
            "FFmpeg: メタデータ埋め込み", path=str(abs_path), metadata=metadata
        )

        temp = abs_path.with_name(f"temp{abs_path.suffix}")
        metadata_args: list[str] = []
        for key, value in metadata.items():
            if value:
                metadata_args.extend(["-metadata", f"{key}={value}"])

        result = await self._run_text(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(abs_path),
                *metadata_args,
                "-c",
                "copy",
                str(temp),
            ]
        )
        if temp.exists():
            abs_path.unlink(missing_ok=True)
            temp.rename(abs_path)
        if result.returncode != 0:
            self._log_failure("FFmpeg: メタデータ埋め込み失敗", result)

    async def get_metadata(self, path: Path) -> Dict[str, str]:
        abs_path = path.resolve()
        self.logger.info("FFmpeg: メタデータ取得", path=str(abs_path))

        result = await self._run_text(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_format",
                "-print_format",
                "json",
                str(abs_path),
            ]
        )
        if result.returncode != 0 or not result.stdout:
            self._log_failure("FFmpeg: メタデータ取得失敗", result)
            return {}

        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            self.logger.error("FFmpeg metadata JSON parse failed")
            return {}

        if not isinstance(data, dict):
            return {}
        format_section = data.get("format")
        if not isinstance(format_section, dict):
            return {}
        tags = format_section.get("tags")
        if not isinstance(tags, dict):
            return {}

        metadata: Dict[str, str] = {}
        for key, value in tags.items():
            if isinstance(key, str) and isinstance(value, str):
                metadata[key.lower()] = value
        return metadata

    async def embed_subtitle(self, path: Path, srt: str) -> None:
        abs_path = path.resolve()
        self.logger.info("FFmpeg: 字幕追加", path=str(abs_path))

        temp = abs_path.with_name(f"temp{abs_path.suffix}")
        result = await self._run_text(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(abs_path),
                "-f",
                "srt",
                "-i",
                "-",
                "-map",
                "0",
                "-map",
                "1",
                "-c",
                "copy",
                "-c:s",
                "srt",
                "-metadata:s:s:0",
                "title=Subtitles",
                str(temp),
            ],
            input_text=srt,
        )
        if temp.exists():
            abs_path.unlink(missing_ok=True)
            temp.rename(abs_path)
        if result.returncode != 0:
            self._log_failure("FFmpeg: 字幕追加失敗", result)

    async def get_subtitle(self, path: Path) -> Optional[str]:
        indices = await self._find_streams(path, "subtitle", "subrip")
        if not indices:
            self.logger.error("FFmpeg subtitle not found", path=str(path))
            return None
        index = indices[0]

        result = await self._run_text(
            [
                "ffmpeg",
                "-i",
                str(path),
                "-map",
                f"0:{index}",
                "-c",
                "copy",
                "-f",
                "srt",
                "pipe:1",
            ]
        )
        if result.returncode != 0:
            self._log_failure("FFmpeg: 字幕取得失敗", result)
            return None
        return result.stdout

    async def embed_thumbnail(self, path: Path, thumbnail: bytes) -> None:
        abs_path = path.resolve()
        self.logger.info("FFmpeg: サムネイル追加", path=str(abs_path))

        temp = abs_path.with_name(f"temp{abs_path.suffix}")
        result = await self._run_binary(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(abs_path),
                "-i",
                "-",
                "-map",
                "0",
                "-map",
                "1",
                "-c",
                "copy",
                str(temp),
            ],
            input_bytes=thumbnail,
        )
        if temp.exists():
            abs_path.unlink(missing_ok=True)
            temp.rename(abs_path)
        if result.returncode != 0:
            self._log_failure("FFmpeg: サムネイル追加失敗", result)

    async def get_thumbnail(self, path: Path) -> Optional[bytes]:
        indices = await self._find_streams(path, "video", "png")
        if not indices:
            self.logger.error("FFmpeg thumbnail not found", path=str(path))
            return None
        index = indices[0]

        result = await self._run_binary(
            [
                "ffmpeg",
                "-i",
                str(path),
                "-map",
                f"0:{index}",
                "-f",
                "image2",
                "-c",
                "copy",
                "pipe:1",
            ]
        )
        if result.returncode != 0:
            self.logger.error(
                "FFmpeg thumbnail extraction failed",
                stderr=result.stderr.decode("utf-8", errors="ignore"),
            )
            return None
        return result.stdout

    async def change_volume(self, path: Path, multiplier: float) -> None:
        abs_path = path.resolve()
        self.logger.info(
            "FFmpeg: 音量変更", path=str(abs_path), multiplier=multiplier
        )
        if multiplier == 1.0:
            return

        temp = abs_path.with_name(f"temp{abs_path.suffix}")
        result = await self._run_text(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(abs_path),
                "-map",
                "0",
                "-c:v",
                "copy",
                "-af",
                f"volume={multiplier}",
                "-c:s",
                "copy",
                str(temp),
            ]
        )
        if temp.exists():
            abs_path.unlink(missing_ok=True)
            temp.rename(abs_path)
        if result.returncode != 0:
            self._log_failure("FFmpeg: 音量変更失敗", result)

    async def get_video_length(self, path: Path) -> Optional[float]:
        abs_path = path.resolve()
        # キャッシュ利用
        cached = self._length_cache.get(abs_path)
        if cached is not None:
            self.logger.debug(
                "FFprobe: 長さ取得 (cache)", path=str(abs_path), seconds=cached
            )
            return cached
        self.logger.debug("FFprobe: 長さ取得", path=str(abs_path))

        result = await self._run_text(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(abs_path),
            ],
            timeout=3,
        )
        if result.returncode != 0:
            self._log_failure("FFprobe: 長さ取得失敗", result)
            self._length_cache[abs_path] = None
            return None

        raw = result.stdout.strip()
        if not raw:
            self.logger.error(
                "FFprobe: 長さ取得失敗 (stdout が空)",
                path=str(abs_path),
            )
            self._length_cache[abs_path] = None
            return None
        try:
            length = float(raw)
        except ValueError:
            self.logger.error("FFprobe: 長さ数値変換失敗", raw=raw)
            self._length_cache[abs_path] = None
            return None
        else:
            self._length_cache[abs_path] = length
            return length

    async def add_audio_track(
        self,
        path: Path,
        audio: Path,
        *,
        stream_title: Optional[str] = None,
    ) -> None:
        abs_path = path.resolve()
        audio_path = audio.resolve()
        self.logger.info(
            "FFmpeg: 音声トラック追加",
            path=str(abs_path),
            audio=str(audio_path),
            stream_title=stream_title,
        )
        temp = abs_path.with_name(f"temp{abs_path.suffix}")
        audio_stream_index = await self._count_streams(abs_path, "audio")

        command: list[str] = [
            "ffmpeg",
            "-y",
            "-i",
            str(abs_path),
            "-i",
            str(audio_path),
            "-map",
            "0:v",
            "-map",
            "0:a?",
            "-map",
            "0:s?",
            "-map",
            "1:a",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-c:s",
            "copy",
        ]
        if stream_title:
            command.extend(
                [
                    f"-metadata:s:a:{audio_stream_index}",
                    f"title={stream_title}",
                ]
            )
        command.append(str(temp))

        result = await self._run_text(command)
        if temp.exists():
            abs_path.unlink(missing_ok=True)
            temp.rename(abs_path)
        if result.returncode != 0:
            self._log_failure("FFmpeg: 音声トラック追加失敗", result)

    async def list_video_devices(self) -> List[str]:
        """List available DirectShow video capture devices.

        Returns:
            List of device names
        """
        self.logger.info("FFmpeg: ビデオデバイス一覧取得")

        result = await self._run_text(
            ["ffmpeg", "-list_devices", "true", "-f", "dshow", "-i", "dummy"],
            timeout=10,
        )

        # Parse the output to extract video device names
        devices: List[str] = []
        lines = result.stderr.split("\n")

        for line in lines:
            # Look for lines with device names marked as (video)
            # Format: [dshow @ ...] "Device Name" (video)
            if "(video)" in line and '"' in line:
                # Extract text between quotes
                start = line.find('"')
                end = line.rfind('"')
                if start != -1 and end != -1 and start < end:
                    device_name = line[start + 1 : end]
                    if device_name and device_name not in devices:
                        devices.append(device_name)

        self.logger.info(f"FFmpeg: {len(devices)}個のビデオデバイスを検出")
        return devices

    # ------------------------------------------------------------------
    # Internal utilities
    # ------------------------------------------------------------------
    async def _find_streams(
        self,
        path: Path,
        codec_type: Literal["video", "audio", "subtitle"],
        codec_name: str,
    ) -> List[int]:
        result = await self._run_text(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_streams",
                "-of",
                "json",
                str(path),
            ]
        )
        if result.returncode != 0 or not result.stdout:
            self.logger.error("FFprobe stream info failed")
            return []

        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            self.logger.error("FFprobe stream JSON parse failed")
            return []
        if not isinstance(data, dict):
            return []
        streams = data.get("streams")
        if not isinstance(streams, list):
            return []

        matching: list[int] = []
        for stream in streams:
            if not isinstance(stream, dict):
                continue
            if stream.get("codec_type") != codec_type:
                continue
            if stream.get("codec_name") != codec_name:
                continue
            index_value = stream.get("index")
            if isinstance(index_value, int):
                matching.append(index_value)
        return matching

    async def _count_streams(
        self,
        path: Path,
        codec_type: Literal["video", "audio", "subtitle"],
    ) -> int:
        result = await self._run_text(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_streams",
                "-of",
                "json",
                str(path),
            ]
        )
        if result.returncode != 0 or not result.stdout:
            self.logger.error("FFprobe stream info failed")
            return 0

        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            self.logger.error("FFprobe stream JSON parse failed")
            return 0
        if not isinstance(data, dict):
            return 0
        streams = data.get("streams")
        if not isinstance(streams, list):
            return 0

        count = 0
        for stream in streams:
            if not isinstance(stream, dict):
                continue
            if stream.get("codec_type") == codec_type:
                count += 1
        return count
