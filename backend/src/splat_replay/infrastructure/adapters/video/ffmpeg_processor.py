"""FFmpeg adapter utilities."""

from __future__ import annotations

import asyncio
import contextlib
import json
import subprocess
import threading
from asyncio import subprocess as asyncio_subprocess
from pathlib import Path
from subprocess import CompletedProcess
from typing import Callable, Dict, List, Literal, Optional, Sequence

from splat_replay.application.interfaces import (
    FramePreviewPort,
    VideoEditorPort,
)
from structlog.stdlib import BoundLogger


class FFmpegProcessor(VideoEditorPort, FramePreviewPort):
    """Provides high-level helpers around ffmpeg/ffprobe commands."""

    def __init__(self, logger: BoundLogger) -> None:
        self.logger = logger
        # 動画長のキャッシュ (GUI リスト表示時の ffprobe 過多を防止)
        self._length_cache: dict[Path, float | None] = {}
        self._subprocess_fallback_logged = False
        self._frame_preview_semaphore = asyncio.Semaphore(1)

    async def _watch_async_process_cancel(
        self,
        process: asyncio_subprocess.Process,
        cancel_check: Callable[[], bool],
    ) -> None:
        while process.returncode is None:
            if cancel_check():
                process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), timeout=2.0)
                except asyncio.TimeoutError:
                    process.kill()
                    await process.wait()
                return
            await asyncio.sleep(0.1)

    @staticmethod
    def _terminate_process(process: subprocess.Popen[bytes]) -> None:
        if process.poll() is not None:
            return
        with contextlib.suppress(Exception):
            process.terminate()
        try:
            process.wait(timeout=2.0)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()

    def _start_cancel_watcher(
        self,
        process: subprocess.Popen[bytes],
        cancel_check: Callable[[], bool] | None,
    ) -> tuple[threading.Event, threading.Thread] | None:
        if cancel_check is None:
            return None
        finished = threading.Event()

        def watch() -> None:
            while not finished.wait(0.1):
                if cancel_check():
                    self._terminate_process(process)
                    return

        thread = threading.Thread(target=watch, daemon=True)
        thread.start()
        return finished, thread

    @staticmethod
    def _stop_cancel_watcher(
        watcher: tuple[threading.Event, threading.Thread] | None,
    ) -> None:
        if watcher is None:
            return
        finished, thread = watcher
        finished.set()
        thread.join()

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
        cancel_check: Callable[[], bool] | None = None,
    ) -> CompletedProcess[str]:
        # Windows環境での asyncio.create_subprocess_exec の NotImplementedError 回避
        # subprocess.run を asyncio.to_thread でラップして実行
        import sys

        if sys.platform == "win32":
            return await self._run_text_windows(
                command,
                cwd=cwd,
                input_text=input_text,
                timeout=timeout,
                cancel_check=cancel_check,
            )

        process = await asyncio.create_subprocess_exec(
            *command,
            cwd=str(cwd) if cwd else None,
            stdin=asyncio_subprocess.PIPE if input_text is not None else None,
            stdout=asyncio_subprocess.PIPE,
            stderr=asyncio_subprocess.PIPE,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        input_bytes = (
            input_text.encode("utf-8") if input_text is not None else None
        )
        cancel_watcher = (
            asyncio.create_task(
                self._watch_async_process_cancel(process, cancel_check)
            )
            if cancel_check is not None
            else None
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
        finally:
            if cancel_watcher is not None:
                cancel_watcher.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await cancel_watcher
        if cancel_check is not None and cancel_check():
            raise asyncio.CancelledError
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
        cancel_check: Callable[[], bool] | None = None,
    ) -> CompletedProcess[str]:
        """Windows環境での subprocess 実行（asyncio.to_thread を使用）。"""

        def run_subprocess() -> CompletedProcess[str]:
            input_bytes = (
                input_text.encode("utf-8") if input_text is not None else None
            )
            if cancel_check is not None and cancel_check():
                raise asyncio.CancelledError
            process = subprocess.Popen(
                list(command),
                cwd=str(cwd) if cwd else None,
                stdin=subprocess.PIPE if input_bytes is not None else None,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            watcher = self._start_cancel_watcher(process, cancel_check)
            try:
                stdout, stderr = process.communicate(
                    input=input_bytes, timeout=timeout
                )
            except subprocess.TimeoutExpired:
                self._terminate_process(process)
                process.communicate()
                raise
            finally:
                self._stop_cancel_watcher(watcher)
            if cancel_check is not None and cancel_check():
                raise asyncio.CancelledError
            return CompletedProcess(
                args=list(command),
                returncode=process.returncode,
                stdout=stdout.decode("utf-8", errors="replace"),
                stderr=stderr.decode("utf-8", errors="replace"),
            )

        return await asyncio.to_thread(run_subprocess)

    async def _run_with_progress(
        self,
        command: Sequence[str],
        total_duration: float,
        on_progress: Callable[[float, Optional[str]], None],
        *,
        cwd: Path | None = None,
        input_bytes: bytes | None = None,
        progress_message: str = "動画を結合中",
        named_message_prefix: str | None = "結合中",
        cancel_check: Callable[[], bool] | None = None,
    ) -> CompletedProcess[str]:
        """FFmpegコマンドを実行し、stderrの出力をリアルタイムにパースして進捗を報告する。"""
        import re
        import subprocess

        # Opening '...' for reading パターン
        opening_re = re.compile(r"Opening '([^']+)' for reading")
        # time=hh:mm:ss.xx パターン (ミリ秒部分の桁数変動に対応)
        time_re = re.compile(r"time=(\d{2}):(\d{2}):(\d{2})(?:\.(\d+))?")

        current_clip_name = ""

        def run_and_parse() -> CompletedProcess[str]:
            nonlocal current_clip_name
            if cancel_check is not None and cancel_check():
                raise asyncio.CancelledError
            # stderrをアンバッファド(bufsize=0)かつバイナリモードで実行
            process = subprocess.Popen(
                list(command),
                cwd=str(cwd) if cwd else None,
                stdin=subprocess.PIPE if input_bytes is not None else None,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            watcher = self._start_cancel_watcher(process, cancel_check)

            stdout_lines: list[bytes] = []
            stderr_lines: list[bytes] = []
            last_percent = -1.0
            stdin_thread: threading.Thread | None = None

            stdin = process.stdin
            if input_bytes is not None and stdin is not None:

                def write_stdin() -> None:
                    try:
                        stdin.write(input_bytes)
                    except BrokenPipeError:
                        pass
                    finally:
                        with contextlib.suppress(Exception):
                            stdin.close()

                stdin_thread = threading.Thread(
                    target=write_stdin, daemon=True
                )
                stdin_thread.start()

            try:
                if process.stderr:
                    line_bytes = bytearray()
                    while True:
                        chunk = process.stderr.read(1)
                        if not chunk:
                            break

                        char_byte = chunk[0]
                        # \r または \n で改行とみなす
                        if char_byte == ord("\r") or char_byte == ord("\n"):
                            if line_bytes:
                                line = line_bytes.decode(
                                    "utf-8", errors="replace"
                                )
                                stderr_lines.append(bytes(line_bytes) + chunk)
                                line_bytes.clear()

                                # A. 処理中のクリップ名検出
                                opening_match = opening_re.search(line)
                                if opening_match:
                                    full_path = opening_match.group(1)
                                    current_clip_name = Path(full_path).name

                                # B. 現在のタイムスタンプ検出と進捗計算
                                time_match = time_re.search(line)
                                if time_match and total_duration > 0:
                                    hh = int(time_match.group(1))
                                    mm = int(time_match.group(2))
                                    ss = int(time_match.group(3))
                                    cs = 0.0
                                    if time_match.group(4):
                                        cs_str = time_match.group(4)
                                        cs = int(cs_str) / (10 ** len(cs_str))
                                    current_seconds = (
                                        hh * 3600 + mm * 60 + ss + cs
                                    )

                                    percent = min(
                                        100.0,
                                        (current_seconds / total_duration)
                                        * 100.0,
                                    )

                                    # 頻度制御: 0.5%以上進捗が進んだ場合、または完了時のみ発行
                                    if (
                                        percent - last_percent >= 0.5
                                        or percent >= 100.0
                                    ):
                                        last_percent = percent
                                        msg = (
                                            f"{named_message_prefix}: {current_clip_name}"
                                            if current_clip_name
                                            and named_message_prefix
                                            is not None
                                            else "動画を結合中"
                                        )
                                        if (
                                            not current_clip_name
                                            or named_message_prefix is None
                                        ):
                                            msg = progress_message
                                        # スレッド安全にコールバックをディスパッチ
                                        loop.call_soon_threadsafe(
                                            on_progress, percent, msg
                                        )
                            else:
                                stderr_lines.append(chunk)
                        else:
                            line_bytes.append(char_byte)

                    if line_bytes:
                        line = line_bytes.decode("utf-8", errors="replace")
                        stderr_lines.append(bytes(line_bytes))
                        # 必要であれば最後の端数行もパース

                # 残りの stdout を回収
                stdout_data = process.stdout.read() if process.stdout else b""
                if stdin_thread is not None:
                    stdin_thread.join()
                process.wait()
                if stdout_data:
                    stdout_lines.append(stdout_data)
            finally:
                self._stop_cancel_watcher(watcher)

            if cancel_check is not None and cancel_check():
                raise asyncio.CancelledError

            stdout_str = b"".join(stdout_lines).decode(
                "utf-8", errors="replace"
            )
            stderr_str = b"".join(stderr_lines).decode(
                "utf-8", errors="replace"
            )

            return CompletedProcess(
                args=list(command),
                returncode=process.returncode,
                stdout=stdout_str,
                stderr=stderr_str,
            )

        loop = asyncio.get_running_loop()
        return await asyncio.to_thread(run_and_parse)

    async def _run_binary(
        self,
        command: Sequence[str],
        *,
        input_bytes: bytes | None = None,
        timeout: float | None = None,
        cancel_check: Callable[[], bool] | None = None,
    ) -> CompletedProcess[bytes]:
        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                stdin=asyncio_subprocess.PIPE
                if input_bytes is not None
                else None,
                stdout=asyncio_subprocess.PIPE,
                stderr=asyncio_subprocess.PIPE,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except NotImplementedError:
            if not self._subprocess_fallback_logged:
                self.logger.warning(
                    "asyncio subprocess が未対応のため同期実行へフォールバックします"
                )
                self._subprocess_fallback_logged = True
            return await self._run_binary_fallback(
                command,
                input_bytes=input_bytes,
                timeout=timeout,
                cancel_check=cancel_check,
            )
        cancel_watcher = (
            asyncio.create_task(
                self._watch_async_process_cancel(process, cancel_check)
            )
            if cancel_check is not None
            else None
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
        finally:
            if cancel_watcher is not None:
                cancel_watcher.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await cancel_watcher
        if cancel_check is not None and cancel_check():
            raise asyncio.CancelledError
        return CompletedProcess(
            args=list(command),
            returncode=process.returncode
            if process.returncode is not None
            else -1,
            stdout=stdout_bytes,
            stderr=stderr_bytes,
        )

    async def _run_binary_fallback(
        self,
        command: Sequence[str],
        *,
        input_bytes: bytes | None = None,
        timeout: float | None = None,
        cancel_check: Callable[[], bool] | None = None,
    ) -> CompletedProcess[bytes]:
        def _run() -> CompletedProcess[bytes]:
            if cancel_check is not None and cancel_check():
                raise asyncio.CancelledError
            process = subprocess.Popen(
                list(command),
                stdin=subprocess.PIPE if input_bytes is not None else None,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            watcher = self._start_cancel_watcher(process, cancel_check)
            try:
                stdout, stderr = process.communicate(
                    input=input_bytes, timeout=timeout
                )
            except subprocess.TimeoutExpired:
                self._terminate_process(process)
                process.communicate()
                raise
            finally:
                self._stop_cancel_watcher(watcher)
            if cancel_check is not None and cancel_check():
                raise asyncio.CancelledError
            return CompletedProcess(
                args=list(command),
                returncode=process.returncode,
                stdout=stdout,
                stderr=stderr,
            )

        return await asyncio.to_thread(_run)

    def _log_failure(
        self,
        message: str,
        result: CompletedProcess[str] | CompletedProcess[bytes],
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

    def _commit_temp_output(
        self,
        original: Path,
        temp: Path,
        result: CompletedProcess[str] | CompletedProcess[bytes],
        failure_message: str,
    ) -> None:
        if result.returncode != 0:
            temp.unlink(missing_ok=True)
            self._log_failure(failure_message, result)
            raise RuntimeError(
                f"{failure_message}: FFmpeg終了コード {result.returncode}"
            )
        if not temp.is_file():
            raise RuntimeError(f"{failure_message}: 出力ファイルがありません")
        temp.replace(original)

    # ------------------------------------------------------------------
    # VideoEditorPort implementation
    # ------------------------------------------------------------------
    async def extract_frame(
        self,
        video: Path,
        seconds: float,
        *,
        max_width: int | None = None,
    ) -> bytes | None:
        """元動画から進捗表示用PNGフレームを抽出する。"""
        abs_video = video.resolve()
        normalized_seconds = max(0, int(seconds))
        normalized_width = (
            max_width if max_width is not None and max_width > 0 else None
        )
        if not abs_video.is_file():
            return None

        command = [
            "ffmpeg",
            "-y",
            "-ss",
            str(normalized_seconds),
            "-i",
            str(abs_video),
            "-vframes",
            "1",
        ]
        if normalized_width is not None:
            command.extend(["-vf", f"scale={normalized_width}:-2"])
        command.extend(["-f", "image2", "-vcodec", "png", "pipe:1"])

        try:
            async with self._frame_preview_semaphore:
                result = await self._run_binary(command, timeout=8)
        except (OSError, subprocess.TimeoutExpired) as exc:
            self.logger.warning(
                "FFmpeg preview frame extraction failed",
                path=str(abs_video),
                seconds=normalized_seconds,
                width=normalized_width,
                error=str(exc),
            )
            return None

        if result.returncode != 0 or not result.stdout:
            self._log_failure("FFmpeg preview frame extraction failed", result)
            return None
        return result.stdout

    async def merge(
        self,
        clips: list[Path],
        output: Path,
        *,
        on_progress: Optional[Callable[[float, Optional[str]], None]] = None,
        cancel_check: Callable[[], bool] | None = None,
    ) -> Path:
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

        command = [
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
        ]

        try:
            if on_progress is not None:
                # 各クリップの動画の長さを事前集計して総秒数を算出
                total_duration = 0.0
                for clip in abs_clips:
                    dur = await self.get_video_length(clip) or 0.0
                    total_duration += dur

                result = await self._run_with_progress(
                    command,
                    total_duration,
                    on_progress,
                    cwd=abs_clips[0].parent,
                    cancel_check=cancel_check,
                )
            else:
                result = await self._run_text(
                    command,
                    cwd=abs_clips[0].parent,
                    cancel_check=cancel_check,
                )
        except asyncio.CancelledError:
            output.unlink(missing_ok=True)
            raise
        finally:
            filelist.unlink(missing_ok=True)
        if result.returncode != 0:
            output.unlink(missing_ok=True)
            self._log_failure("FFmpeg: 結合に失敗", result)
            raise RuntimeError(
                f"FFmpeg: 結合に失敗: FFmpeg終了コード {result.returncode}"
            )
        return output

    async def embed_metadata(
        self,
        path: Path,
        metadata: Dict[str, str],
        *,
        cancel_check: Callable[[], bool] | None = None,
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

        try:
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
                ],
                cancel_check=cancel_check,
            )
        except asyncio.CancelledError:
            temp.unlink(missing_ok=True)
            raise
        self._commit_temp_output(
            abs_path, temp, result, "FFmpeg: メタデータ埋め込み失敗"
        )

    async def embed_metadata_and_thumbnail(
        self,
        path: Path,
        metadata: Dict[str, str],
        thumbnail: bytes,
        *,
        on_progress: Optional[Callable[[float, Optional[str]], None]] = None,
        cancel_check: Callable[[], bool] | None = None,
    ) -> None:
        abs_path = path.resolve()
        self.logger.info(
            "FFmpeg: メタデータ・サムネイル埋め込み",
            path=str(abs_path),
            metadata=metadata,
        )

        temp = abs_path.with_name(f"temp{abs_path.suffix}")
        metadata_args: list[str] = []
        for key, value in metadata.items():
            if value:
                metadata_args.extend(["-metadata", f"{key}={value}"])

        command = [
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
            *metadata_args,
            "-c",
            "copy",
            str(temp),
        ]

        try:
            if on_progress is not None:
                total_duration = await self.get_video_length(abs_path) or 0.0
                result = await self._run_with_progress(
                    command,
                    total_duration,
                    on_progress,
                    input_bytes=thumbnail,
                    progress_message="メタデータ・サムネイルを埋め込み中",
                    named_message_prefix=None,
                    cancel_check=cancel_check,
                )
                if result.returncode == 0:
                    on_progress(100.0, "メタデータ・サムネイルを埋め込み中")
            else:
                result = await self._run_binary(
                    command,
                    input_bytes=thumbnail,
                    cancel_check=cancel_check,
                )
        except asyncio.CancelledError:
            temp.unlink(missing_ok=True)
            raise
        self._commit_temp_output(
            abs_path,
            temp,
            result,
            "FFmpeg: メタデータ・サムネイル埋め込み失敗",
        )

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

    async def embed_subtitle(
        self,
        path: Path,
        srt: str,
        *,
        cancel_check: Callable[[], bool] | None = None,
    ) -> None:
        abs_path = path.resolve()
        self.logger.info("FFmpeg: 字幕追加", path=str(abs_path))

        temp = abs_path.with_name(f"temp{abs_path.suffix}")
        try:
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
                cancel_check=cancel_check,
            )
        except asyncio.CancelledError:
            temp.unlink(missing_ok=True)
            raise
        self._commit_temp_output(
            abs_path, temp, result, "FFmpeg: 字幕追加失敗"
        )

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

    async def embed_thumbnail(
        self,
        path: Path,
        thumbnail: bytes,
        *,
        cancel_check: Callable[[], bool] | None = None,
    ) -> None:
        abs_path = path.resolve()
        self.logger.info("FFmpeg: サムネイル追加", path=str(abs_path))

        temp = abs_path.with_name(f"temp{abs_path.suffix}")
        try:
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
                cancel_check=cancel_check,
            )
        except asyncio.CancelledError:
            temp.unlink(missing_ok=True)
            raise
        self._commit_temp_output(
            abs_path, temp, result, "FFmpeg: サムネイル追加失敗"
        )

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

    async def change_volume(
        self,
        path: Path,
        multiplier: float,
        *,
        cancel_check: Callable[[], bool] | None = None,
    ) -> None:
        abs_path = path.resolve()
        self.logger.info(
            "FFmpeg: 音量変更", path=str(abs_path), multiplier=multiplier
        )
        if multiplier == 1.0:
            return

        temp = abs_path.with_name(f"temp{abs_path.suffix}")
        try:
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
                ],
                cancel_check=cancel_check,
            )
        except asyncio.CancelledError:
            temp.unlink(missing_ok=True)
            raise
        self._commit_temp_output(
            abs_path, temp, result, "FFmpeg: 音量変更失敗"
        )

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
        cancel_check: Callable[[], bool] | None = None,
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

        try:
            result = await self._run_text(command, cancel_check=cancel_check)
        except asyncio.CancelledError:
            temp.unlink(missing_ok=True)
            raise
        self._commit_temp_output(
            abs_path, temp, result, "FFmpeg: 音声トラック追加失敗"
        )

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
