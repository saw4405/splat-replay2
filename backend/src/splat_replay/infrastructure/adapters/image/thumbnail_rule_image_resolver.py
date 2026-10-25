"""同梱したルール名画像を検証する。フォントは読み込まない。"""

from pathlib import Path
from PIL import Image


class ThumbnailRuleImageResolver:
    """高さ135px・幅532px以下の白文字透明PNGのみを受け付ける。"""

    def resolve(self, preferred_path: Path) -> Path | None:
        try:
            with Image.open(preferred_path) as image:
                if image.format != "PNG" or image.mode != "RGBA":
                    return None
                width, height = image.size
                if height != 135 or not 0 < width <= 532:
                    return None
                alpha = image.getchannel("A")
                if alpha.getbbox() != (0, 0, width, height):
                    return None
                if alpha.getextrema() != (0, 255):
                    return None
                for channel in image.convert("RGB").split():
                    if channel.getextrema() != (255, 255):
                        return None
                return preferred_path
        except (OSError, ValueError):
            return None
