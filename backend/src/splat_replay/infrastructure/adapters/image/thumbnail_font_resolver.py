"""サムネイル描画に使える日本語フォントを解決する。"""

from __future__ import annotations

import os
from pathlib import Path
import sys

from PIL import ImageFont


_MACOS_FONT_PATHS: tuple[Path, ...] = (
    Path("/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc"),
    Path("/System/Library/Fonts/ヒラギノ角ゴシック W4.ttc"),
    Path("/System/Library/Fonts/ヒラギノ丸ゴ ProN W4.ttc"),
)
_WINDOWS_FONT_FILENAMES: tuple[str, ...] = (
    "YuGothR.ttc",
    "YuGothM.ttc",
    "meiryo.ttc",
    "msgothic.ttc",
)


def _system_font_candidates() -> tuple[Path, ...]:
    if sys.platform == "darwin":
        return _MACOS_FONT_PATHS
    if sys.platform == "win32":
        fonts_dir = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
        return tuple(fonts_dir / name for name in _WINDOWS_FONT_FILENAMES)
    return ()


class ThumbnailFontResolver:
    """Pillow で読み込める指定フォントまたは OS フォントを返す。"""

    def resolve(self, preferred_path: Path) -> Path | None:
        for candidate in (preferred_path, *_system_font_candidates()):
            if not candidate.is_file():
                continue
            try:
                font = ImageFont.truetype(str(candidate), 140)
                if font.getmask("日本語").getbbox() is not None:
                    return candidate
            except (OSError, ValueError):
                continue
        return None
