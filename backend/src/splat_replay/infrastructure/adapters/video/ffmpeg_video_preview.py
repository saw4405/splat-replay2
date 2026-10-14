"""FFmpeg による一時 MP4 プレビュー生成。"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
import os
import shutil
import tempfile
import uuid
from asyncio import subprocess as asyncio_subprocess
from pathlib import Path
from typing import cast

from splat_replay.application.interfaces import (
    VideoPreviewError,
    VideoPreviewPort,
    VideoPreviewUnavailableError,
)
from structlog.stdlib import BoundLogger


class FFmpegVideoPreviewAdapter(VideoPreviewPort):
    """MKV を検査し、必要な場合だけ H.264 / AAC の MP4 に変換する。"""

    def __init__(self, logger: BoundLogger) -> None:
        self._logger = logger
        self._temporary_directory = tempfile.TemporaryDirectory(
            prefix="splat-replay-preview-"
        )
        self._cache_dir = Path(self._temporary_directory.name)
        self._inflight: dict[str, asyncio.Task[Path]] = {}
        self._waiters: dict[str, int] = {}
        self._inflight_lock = asyncio.Lock()
        self._closed = False

    async def create_mp4_preview(self, source: Path) -> Path:
        """入力の更新状態を含むキーで生成を共有する。"""
        if self._closed:
            raise VideoPreviewError("Video preview service is closed")
        source = source.resolve()
        signature = self._signature(source)
        key = hashlib.sha256(
            f"{source}\0{signature}".encode("utf-8")
        ).hexdigest()
        output = self._cache_dir / f"{key}.mp4"
        if output.is_file():
            if self._signature(source) == signature:
                return output
            raise VideoPreviewError("Source video changed during preview")

        async with self._inflight_lock:
            task = self._inflight.get(key)
            if task is None:
                task = asyncio.create_task(
                    self._create_preview(source, signature, key, output)
                )
                self._inflight[key] = task
                self._waiters[key] = 0
                task.add_done_callback(
                    lambda done, task_key=key: self._forget_task(
                        task_key, done
                    )
                )
            self._waiters[key] += 1
        try:
            return await asyncio.shield(task)
        finally:
            async with self._inflight_lock:
                if key in self._waiters:
                    remaining = self._waiters[key] - 1
                    if remaining == 0:
                        self._waiters.pop(key, None)
                        if not task.done():
                            task.cancel()
                    else:
                        self._waiters[key] = remaining

    @staticmethod
    def _signature(source: Path) -> tuple[int, int, int, int, int]:
        try:
            stat = source.stat()
        except OSError as exc:
            raise VideoPreviewError(
                f"Source video is unavailable: {source}"
            ) from exc
        if not source.is_file():
            raise VideoPreviewError(f"Source video is unavailable: {source}")
        return (
            stat.st_dev,
            stat.st_ino,
            stat.st_size,
            stat.st_mtime_ns,
            stat.st_ctime_ns,
        )

    def _forget_task(self, key: str, task: asyncio.Task[Path]) -> None:
        if self._inflight.get(key) is task:
            del self._inflight[key]
            self._waiters.pop(key, None)
        if not task.cancelled():
            # Consume failures if every HTTP waiter was cancelled.
            task.exception()

    async def _create_preview(
        self,
        source: Path,
        signature: tuple[int, int, int, int, int],
        key: str,
        output: Path,
    ) -> Path:
        ffmpeg = shutil.which("ffmpeg")
        ffprobe = shutil.which("ffprobe")
        if ffmpeg is None or ffprobe is None:
            missing = "ffmpeg" if ffmpeg is None else "ffprobe"
            raise VideoPreviewUnavailableError(
                f"{missing} が見つかりません。FFmpeg をインストールしてください。"
            )

        partial = self._cache_dir / f"{key}.{uuid.uuid4().hex}.partial.mp4"
        try:
            streams = await self._probe(ffprobe, source)
            video_stream = next(
                (
                    stream
                    for stream in streams
                    if stream.get("codec_type") == "video"
                ),
                {},
            )
            video_codec = video_stream.get("codec_name")
            audio_codec = next(
                (
                    stream.get("codec_name")
                    for stream in streams
                    if stream.get("codec_type") == "audio"
                ),
                None,
            )
            if not video_codec:
                raise VideoPreviewError("Source video has no video stream")

            command = [
                ffmpeg,
                "-hide_banner",
                "-nostdin",
                "-y",
                "-i",
                str(source),
                "-map",
                "0:v:0",
                "-map",
                "0:a:0?",
                "-sn",
                "-dn",
            ]
            command.extend(
                ["-c:v", "copy"]
                if video_codec == "h264"
                and video_stream.get("pix_fmt") == "yuv420p"
                else [
                    "-c:v",
                    "libx264",
                    "-preset",
                    "veryfast",
                    "-crf",
                    "23",
                    "-pix_fmt",
                    "yuv420p",
                ]
            )
            if audio_codec:
                command.extend(
                    ["-c:a", "copy"]
                    if audio_codec == "aac"
                    else ["-c:a", "aac", "-b:a", "192k"]
                )
            command.extend(["-movflags", "+faststart", str(partial)])

            await self._run(ffmpeg, command)
            if self._signature(source) != signature:
                raise VideoPreviewError("Source video changed during preview")
            if not partial.is_file() or partial.stat().st_size == 0:
                raise VideoPreviewError("FFmpeg produced an empty MP4 preview")
            os.replace(partial, output)
            self._logger.info(
                "一時 MP4 プレビューを生成しました",
                source=str(source),
                output=str(output),
                video_codec=video_codec,
                audio_codec=audio_codec,
            )
            return output
        except asyncio.CancelledError:
            raise
        except VideoPreviewError:
            raise
        except OSError as exc:
            raise VideoPreviewError(
                f"MP4 preview generation failed: {exc}"
            ) from exc
        finally:
            with contextlib.suppress(FileNotFoundError):
                partial.unlink()

    async def _probe(self, ffprobe: str, source: Path) -> list[dict[str, str]]:
        result = await self._run(
            ffprobe,
            [
                ffprobe,
                "-v",
                "error",
                "-show_entries",
                "stream=codec_type,codec_name,pix_fmt",
                "-of",
                "json",
                str(source),
            ],
        )
        try:
            payload = cast(dict[str, object], json.loads(result))
            streams = cast(list[dict[str, str]], payload["streams"])
        except (KeyError, TypeError, json.JSONDecodeError) as exc:
            raise VideoPreviewError(
                "FFprobe returned invalid stream data"
            ) from exc
        return streams

    async def _run(self, executable: str, command: list[str]) -> str:
        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio_subprocess.PIPE,
                stderr=asyncio_subprocess.PIPE,
            )
        except FileNotFoundError as exc:
            raise VideoPreviewUnavailableError(
                f"{Path(executable).name} が実行できません。FFmpeg を確認してください。"
            ) from exc

        communication = asyncio.create_task(process.communicate())
        try:
            stdout, stderr = await asyncio.shield(communication)
        except asyncio.CancelledError:
            if process.returncode is None:
                process.terminate()
            try:
                await asyncio.wait_for(
                    asyncio.shield(communication), timeout=2
                )
            except TimeoutError:
                process.kill()
                await communication
            raise

        if process.returncode:
            detail = stderr.decode("utf-8", errors="replace")[-2000:].strip()
            raise VideoPreviewError(
                f"{Path(executable).name} failed: {detail or process.returncode}"
            )
        return stdout.decode("utf-8", errors="replace")

    async def close(self) -> None:
        """実行中処理を停止してプロセス専用の一時領域を削除する。"""
        if self._closed:
            return
        self._closed = True
        tasks = tuple(self._inflight.values())
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        await asyncio.to_thread(self._temporary_directory.cleanup)
