"""FFmpeg adapter utilities."""

from __future__ import annotations

import json
import subprocess
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
    def _run_text(
        self,
        command: Sequence[str],
        *,
        cwd: Path | None = None,
        input_text: str | None = None,
        timeout: float | None = None,
    ) -> CompletedProcess[str]:
        return subprocess.run(
            list(command),
            check=False,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            encoding="utf-8",
            input=input_text,
            timeout=timeout,
        )

    def _run_binary(
        self,
        command: Sequence[str],
        *,
        input_bytes: bytes | None = None,
    ) -> CompletedProcess[bytes]:
        return subprocess.run(
            list(command),
            check=False,
            capture_output=True,
            input=input_bytes,
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
    def merge(self, clips: list[Path], output: Path) -> Path:
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

        result = self._run_text(
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

    def embed_metadata(self, path: Path, metadata: Dict[str, str]) -> None:
        abs_path = path.resolve()
        self.logger.info(
            "FFmpeg: メタデータ埋め込み", path=str(abs_path), metadata=metadata
        )

        temp = abs_path.with_name(f"temp{abs_path.suffix}")
        metadata_args: list[str] = []
        for key, value in metadata.items():
            if value:
                metadata_args.extend(["-metadata", f"{key}={value}"])

        result = self._run_text(
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

    def get_metadata(self, path: Path) -> Dict[str, str]:
        abs_path = path.resolve()
        self.logger.info("FFmpeg: メタデータ取得", path=str(abs_path))

        result = self._run_text(
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
            self.logger.error("FFmpeg: メタデータ JSON parse 失敗")
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

    def embed_subtitle(self, path: Path, srt: str) -> None:
        abs_path = path.resolve()
        self.logger.info("FFmpeg: 字幕追加", path=str(abs_path))

        temp = abs_path.with_name(f"temp{abs_path.suffix}")
        result = self._run_text(
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

    def get_subtitle(self, path: Path) -> Optional[str]:
        indices = self._find_streams(path, "subtitle", "subrip")
        if not indices:
            self.logger.error("FFmpeg: 字幕が見つかりません")
            return None
        index = indices[0]

        result = self._run_text(
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

    def embed_thumbnail(self, path: Path, thumbnail: bytes) -> None:
        abs_path = path.resolve()
        self.logger.info("FFmpeg: サムネイル追加", path=str(abs_path))

        temp = abs_path.with_name(f"temp{abs_path.suffix}")
        result = self._run_binary(
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

    def get_thumbnail(self, path: Path) -> Optional[bytes]:
        indices = self._find_streams(path, "video", "png")
        if not indices:
            self.logger.error("FFmpeg: サムネイルが見つかりません")
            return None
        index = indices[0]

        result = self._run_binary(
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
                f"FFmpeg: サムネイル取得失敗: {result.stderr.decode('utf-8', errors='ignore')}"
            )
            return None
        return result.stdout

    def change_volume(self, path: Path, multiplier: float) -> None:
        abs_path = path.resolve()
        self.logger.info(
            "FFmpeg: 音量変更", path=str(abs_path), multiplier=multiplier
        )
        if multiplier == 1.0:
            return

        temp = abs_path.with_name(f"temp{abs_path.suffix}")
        result = self._run_text(
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

    def get_video_length(self, path: Path) -> Optional[float]:
        abs_path = path.resolve()
        # キャッシュ利用
        cached = self._length_cache.get(abs_path)
        if cached is not None:
            self.logger.info(
                "FFprobe: 長さ取得 (cache)", path=str(abs_path), seconds=cached
            )
            return cached
        self.logger.info("FFprobe: 長さ取得", path=str(abs_path))

        result = self._run_text(
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
        try:
            length = float(raw)
        except ValueError:
            self.logger.error("FFprobe: 長さ数値変換失敗", raw=raw)
            self._length_cache[abs_path] = None
            return None
        else:
            self._length_cache[abs_path] = length
            return length

    def add_audio_track(
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
        audio_stream_index = self._count_streams(abs_path, "audio")

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
            "-shortest",
        ]
        if stream_title:
            command.extend(
                [
                    f"-metadata:s:a:{audio_stream_index}",
                    f"title={stream_title}",
                ]
            )
        command.append(str(temp))

        result = self._run_text(command)
        if temp.exists():
            abs_path.unlink(missing_ok=True)
            temp.rename(abs_path)
        if result.returncode != 0:
            self._log_failure("FFmpeg: 音声トラック追加失敗", result)

    # ------------------------------------------------------------------
    # Internal utilities
    # ------------------------------------------------------------------
    def _find_streams(
        self,
        path: Path,
        codec_type: Literal["video", "audio", "subtitle"],
        codec_name: str,
    ) -> List[int]:
        result = self._run_text(
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
            self.logger.error("FFprobe: ストリーム情報取得失敗")
            return []

        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            self.logger.error("FFprobe: ストリーム JSON parse 失敗")
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

    def _count_streams(
        self,
        path: Path,
        codec_type: Literal["video", "audio", "subtitle"],
    ) -> int:
        result = self._run_text(
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
            self.logger.error("FFprobe: ストリーム情報取得失敗")
            return 0

        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            self.logger.error("FFprobe: ストリーム JSON parse 失敗")
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
