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

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _run_text(
        self,
        command: Sequence[str],
        *,
        cwd: Path | None = None,
        input_text: str | None = None,
    ) -> CompletedProcess[str]:
        return subprocess.run(
            list(command),
            check=False,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            encoding="utf-8",
            input=input_text,
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
            "FFmpeg 蜍慕判邨仙粋", clips=[str(c) for c in abs_clips]
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
            self._log_failure("蜍慕判邨仙粋縺ｫ螟ｱ謨・", result)
        return output

    def embed_metadata(self, path: Path, metadata: Dict[str, str]) -> None:
        abs_path = path.resolve()
        self.logger.info(
            "FFmpeg 繝｡繧ｿ繝・・繧ｿ蝓九ａ霎ｼ縺ｿ",
            path=str(abs_path),
            metadata=metadata,
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
            self._log_failure(
                "繝｡繧ｿ繝・・繧ｿ縺ｮ蝓九ａ霎ｼ縺ｿ縺ｫ螟ｱ謨・", result
            )

    def get_metadata(self, path: Path) -> Dict[str, str]:
        abs_path = path.resolve()
        self.logger.info("FFmpeg 繝｡繧ｿ繝・・繧ｿ蜿門ｾ・", path=str(abs_path))

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
            self._log_failure("繝｡繧ｿ繝・・繧ｿ縺ｮ蜿門ｾ励↓螟ｱ謨・", result)
            return {}

        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            self.logger.error("JSON隗｣譫蝉ｸｭ縺ｫ繧ｨ繝ｩ繝ｼ縺檎匱逕溘＠縺ｾ縺励◆")
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
        self.logger.info("FFmpeg �����ǉ�", path=str(abs_path))

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
            self._log_failure("�����̒ǉ��Ɏ��s", result)

    def get_subtitle(self, path: Path) -> Optional[str]:
        indices = self._find_streams(path, "subtitle", "subrip")
        if not indices:
            self.logger.error("������������܂���ł���")
            return None
        index = indices[0]

        result = self._run_text(
            [
                "ffmpeg",
                "-i",
                str(path),
                "-map",
                f"0:s:{index}",
                "-c",
                "copy",
                "-f",
                "srt",
                "pipe:1",
            ]
        )
        if result.returncode != 0:
            self._log_failure("�����̎擾�Ɏ��s", result)
            return None
        return result.stdout

    def embed_thumbnail(self, path: Path, thumbnail: bytes) -> None:
        abs_path = path.resolve()
        self.logger.info("FFmpeg �T���l�C���ǉ�", path=str(abs_path))

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
            self._log_failure("�T���l�C���̒ǉ��Ɏ��s", result)

    def get_thumbnail(self, path: Path) -> Optional[bytes]:
        indices = self._find_streams(path, "video", "png")
        if not indices:
            self.logger.error("�T���l�C����������܂���ł���")
            return None
        index = indices[0]

        result = self._run_binary(
            [
                "ffmpeg",
                "-i",
                str(path),
                "-map",
                f"0:v:{index}",
                "-f",
                "image2",
                "-c",
                "copy",
                "pipe:1",
            ]
        )
        if result.returncode != 0:
            self.logger.error(
                f"�T���l�C���̎擾�Ɏ��s���܂���: {result.stderr.decode('utf-8', errors='ignore')}"
            )
            return None
        return result.stdout

    def change_volume(self, path: Path, multiplier: float) -> None:
        abs_path = path.resolve()
        self.logger.info(
            "FFmpeg ���ʕύX", path=str(abs_path), multiplier=multiplier
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
            self._log_failure("���ʂ̕ύX�Ɏ��s", result)

    def get_video_length(self, path: Path) -> Optional[float]:
        abs_path = path.resolve()
        self.logger.info("FFmpeg ���撷���擾", path=str(abs_path))

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
            ]
        )
        if result.returncode != 0:
            self._log_failure("����̒����̎擾�Ɏ��s", result)
            return None

        try:
            return float(result.stdout.strip())
        except ValueError:
            self.logger.error("����̒����̉�͂Ɏ��s���܂���")
            return None

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
            self.logger.error(
                "繧ｹ繝医Μ繝ｼ繝諠・ｱ縺ｮ蜿門ｾ励↓螟ｱ謨励＠縺ｾ縺励◆"
            )
            return []

        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            self.logger.error("JSON隗｣譫蝉ｸｭ縺ｫ繧ｨ繝ｩ繝ｼ縺檎匱逕溘＠縺ｾ縺励◆")
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
