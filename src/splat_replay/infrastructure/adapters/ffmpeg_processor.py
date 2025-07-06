"""FFmpeg 実行アダプタ。"""

from __future__ import annotations

from pathlib import Path

from splat_replay.shared.logger import get_logger

logger = get_logger()


class FFmpegProcessor:
    """FFmpeg を呼び出して動画加工を行うアダプタ."""

    def merge(self, clips: list[Path]) -> Path:
        """動画を結合する."""
        logger.info("FFmpeg 動画結合", clips=[str(c) for c in clips])
        if not clips:
            raise ValueError("clips is empty")
        filelist = clips[0].parent / "concat.txt"
        filelist.write_text("\n".join([f"file '{c}'" for c in clips]))
        output = (
            clips[0].parent / f"merged_{int(clips[0].stat().st_mtime)}.mp4"
        )
        import subprocess

        subprocess.run(
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
                str(output),
            ],
            check=False,
        )
        filelist.unlink()
        return output

    def embed_metadata(self, path: Path, title: str, comment: str) -> None:
        """タイトルと説明を動画へ埋め込む."""
        logger.info(
            "FFmpeg メタデータ埋め込み",
            path=str(path),
            title=title,
            comment=comment,
        )
        import subprocess

        temp = path.with_name(f"temp{path.suffix}")
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(path),
                "-metadata",
                f"title={title}",
                "-metadata",
                f"comment={comment}",
                "-c",
                "copy",
                str(temp),
            ],
            check=False,
        )
        if temp.exists():
            path.unlink(missing_ok=True)
            temp.rename(path)

    def embed_subtitle(self, path: Path, subtitle: Path) -> None:
        """字幕を動画へ追加する."""
        logger.info("FFmpeg 字幕追加", path=str(path), subtitle=str(subtitle))
        import subprocess

        temp = path.with_name(f"temp{path.suffix}")
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(path),
                "-f",
                "srt",
                "-i",
                str(subtitle),
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
        )
        if temp.exists():
            path.unlink(missing_ok=True)
            temp.rename(path)

    def embed_thumbnail(self, path: Path, thumbnail: Path) -> None:
        """サムネイル画像を動画へ埋め込む."""
        logger.info(
            "FFmpeg サムネイル追加", path=str(path), thumbnail=str(thumbnail)
        )
        import subprocess

        temp = path.with_name(f"temp{path.suffix}")
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(path),
                "-i",
                str(thumbnail),
                "-map",
                "0",
                "-map",
                "1",
                "-c",
                "copy",
                str(temp),
            ],
            check=False,
        )
        if temp.exists():
            path.unlink(missing_ok=True)
            temp.rename(path)

    def change_volume(self, path: Path, multiplier: float) -> None:
        """動画の音量を変更する."""
        logger.info("FFmpeg 音量変更", path=str(path), multiplier=multiplier)
        if multiplier == 1.0:
            return
        import subprocess

        temp = path.with_name(f"temp{path.suffix}")
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(path),
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
        )
        if temp.exists():
            path.unlink(missing_ok=True)
            temp.rename(path)
