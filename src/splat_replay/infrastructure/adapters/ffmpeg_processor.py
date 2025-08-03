"""FFmpeg 実行アダプタ。"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import List, Literal, Optional

from structlog.stdlib import BoundLogger
from splat_replay.application.interfaces import VideoEditorPort


class FFmpegProcessor(VideoEditorPort):
    """FFmpeg を呼び出して動画加工を行うアダプタ."""

    def __init__(self, logger: BoundLogger) -> None:
        self.logger = logger

    def merge(self, clips: list[Path], output: Path) -> Path:
        """動画を結合する."""
        abs_clips = [c.resolve() for c in clips]
        self.logger.info("FFmpeg 動画結合", clips=[str(c) for c in abs_clips])
        if not abs_clips:
            raise ValueError("clips is empty")
        filelist = abs_clips[0].parent / "concat.txt"
        filelist.write_text(
            "\n".join([f"file '{str(c)}'" for c in abs_clips]), encoding="utf-8")
        abs_output = output.resolve()

        result = subprocess.run(
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
                str(abs_output),
            ],
            check=False,
            cwd=str(abs_clips[0].parent),
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        filelist.unlink()
        if result.returncode != 0:
            self.logger.error(
                "動画結合に失敗",
                error=result.stderr,
                output=result.stdout,
            )
        return output

    def embed_metadata(self, path: Path, metadata: dict[str, str]):
        """タイトルと説明を動画へ埋め込む."""
        abs_path = path.resolve()
        self.logger.info(
            "FFmpeg メタデータ埋め込み",
            path=str(abs_path),
            metadata=metadata,
        )

        temp = abs_path.with_name(f"temp{abs_path.suffix}")
        result = subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(abs_path),
                *[
                    item
                    for key, value in metadata.items()
                    if value
                    for item in ("-metadata", f"{key}={value}")
                ],
                "-c",
                "copy",
                str(temp),
            ],
            check=False,
            text=True,
            encoding="utf-8",
        )
        if temp.exists():
            abs_path.unlink(missing_ok=True)
            temp.rename(abs_path)
        if result.returncode != 0:
            self.logger.error(
                "メタデータの埋め込みに失敗",
                error=result.stderr,
                output=result.stdout,
            )

    def get_metadata(self, path: Path) -> dict[str, str]:
        """動画のメタデータを取得する."""
        abs_path = path.resolve()
        self.logger.info("FFmpeg メタデータ取得", path=str(abs_path))

        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_format",
                "-print_format",
                "json",
                str(abs_path),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        if result.returncode != 0 or not result.stdout:
            self.logger.error(
                "メタデータの取得に失敗",
                error=result.stderr,
                output=result.stdout,
            )
            return {}

        data = json.loads(result.stdout)
        tags = data["format"].get("tags", {})
        metadata = {k.lower(): v for k, v in tags.items()}
        return metadata

    def embed_subtitle(self, path: Path, srt: str):
        """字幕を動画へ追加する."""
        abs_path = path.resolve()
        self.logger.info("FFmpeg 字幕追加", path=str(abs_path))

        temp = abs_path.with_name(f"temp{abs_path.suffix}")
        result = subprocess.run(
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
            check=False,
            input=srt,
            text=True,
            encoding="utf-8",
        )
        if temp.exists():
            abs_path.unlink(missing_ok=True)
            temp.rename(abs_path)
        if result.returncode != 0:
            self.logger.error(
                "字幕の追加に失敗",
                error=result.stderr,
                output=result.stdout,
            )

    def get_subtitle(self, path: Path) -> Optional[str]:
        result = self._find_streams(path, "subtitle", "subrip")
        if len(result) == 0:
            self.logger.error("字幕が見つかりませんでした")
            return None
        index = result[0]

        result = subprocess.run(
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
            ],
            capture_output=True,
            text=True,
            encoding="utf-8"
        )
        if result.returncode != 0:
            self.logger.error(
                "字幕の取得に失敗",
                error=result.stderr,
                output=result.stdout,
            )
            return None

        return result.stdout

    def embed_thumbnail(self, path: Path, thumbnail: bytes):
        """サムネイル画像を動画へ埋め込む."""
        abs_path = path.resolve()
        self.logger.info("FFmpeg サムネイル追加", path=str(abs_path))

        temp = abs_path.with_name(f"temp{abs_path.suffix}")
        result = subprocess.run(
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
            check=False,
            input=thumbnail,
        )
        if temp.exists():
            abs_path.unlink(missing_ok=True)
            temp.rename(abs_path)
        if result.returncode != 0:
            self.logger.error(
                "サムネイルの追加に失敗",
                error=result.stderr,
                output=result.stdout,
            )

    def get_thumbnail(self, path: Path) -> Optional[bytes]:
        result = self._find_streams(path, "video", "png")
        if len(result) == 0:
            self.logger.error("サムネイルが見つかりませんでした")
            return None
        index = result[0]
        result = subprocess.run(
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
            ],
            capture_output=True
        )
        if result.returncode != 0:
            self.logger.error(
                f"サムネイルの取得に失敗しました: {result.stderr.decode('utf-8')}"
            )
            return None

        return result.stdout

    def change_volume(self, path: Path, multiplier: float):
        """動画の音量を変更する."""
        abs_path = path.resolve()
        self.logger.info(
            "FFmpeg 音量変更", path=str(abs_path), multiplier=multiplier
        )
        if multiplier == 1.0:
            return

        temp = abs_path.with_name(f"temp{abs_path.suffix}")
        result = subprocess.run(
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
            check=False,
            text=True,
            encoding="utf-8",
        )
        if temp.exists():
            abs_path.unlink(missing_ok=True)
            temp.rename(abs_path)
        if result.returncode != 0:
            self.logger.error(
                "音量の変更に失敗",
                error=result.stderr,
                output=result.stdout,
            )

    def get_video_length(self, path: Path) -> Optional[float]:
        """動画の長さを取得する."""
        abs_path = path.resolve()
        self.logger.info("FFmpeg 動画長さ取得", path=str(abs_path))

        result = subprocess.run(
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
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        if result.returncode != 0:
            self.logger.error(
                "動画の長さの取得に失敗",
                error=result.stderr,
                output=result.stdout,
            )
            return None

        try:
            return float(result.stdout.strip())
        except ValueError:
            self.logger.error("動画の長さの解析に失敗しました")
            return None

    def _find_streams(
        self,
        path: Path,
        codec_type: Literal["video", "audio", "subtitle"],
        codec_name: str,
    ) -> List[int]:
        command = [
            "ffprobe",
            "-v",
            "error",
            "-show_streams",
            "-of",
            "json",
            str(path),
        ]
        result = subprocess.run(
            command, capture_output=True, text=True, encoding="utf-8"
        )
        if result.returncode != 0:
            self.logger.error("ストリーム情報の取得に失敗しました")
            return []

        try:
            info = json.loads(result.stdout)
        except Exception:
            self.logger.error("JSON解析中にエラーが発生しました")
            return []

        target_streams = [
            stream
            for stream in info["streams"]
            if stream.get("codec_type") == codec_type
        ]
        relative_indices = [
            i
            for i, stream in enumerate(target_streams)
            if stream.get("codec_name") == codec_name
        ]

        return relative_indices
