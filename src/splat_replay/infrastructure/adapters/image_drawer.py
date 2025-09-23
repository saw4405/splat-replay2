from __future__ import annotations

from pathlib import Path
from typing import Callable, Iterable, List, Optional, Tuple, TypeVar, cast

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from splat_replay.application.interfaces import ImageDrawerPort, Color


class ImageDrawer(ImageDrawerPort):
    @staticmethod
    def select_brightest_image(
        paths: List[Path], target_rect: Tuple[float, float, float, float]
    ) -> Optional["ImageDrawer"]:
        """
        target_rect: (left, top, right, bottom)
        各値は 0.0〜1.0 なら比率、1.0より大きければピクセル値として扱う。
        例:
        (0, 0, 750, 1.0) → 左端から750px, 全高
        (0.5, 0, 1.0, 1.0) → 画像の右半分
        """

        def to_px(val: float, maxval: int) -> int:
            if 0.0 <= val <= 1.0:
                return int(val * maxval)
            return int(min(val, maxval))

        best_img = None
        best_score = -1.0
        for path in paths:
            if not path.exists():
                continue
            img = Image.open(path).convert("RGB")
            img_hsv = img.convert("HSV")
            width, height = img_hsv.size
            left, top, right, bottom = target_rect
            x0 = to_px(left, width)
            y0 = to_px(top, height)
            x1 = to_px(right, width)
            y1 = to_px(bottom, height)
            # right/bottomがleft/topより小さい場合はmax値にする
            x1 = max(x1, x0 + 1)
            y1 = max(y1, y0 + 1)
            x1 = min(x1, width)
            y1 = min(y1, height)
            cropped_image = img_hsv.crop((x0, y0, x1, y1))
            pixel_array = np.array(cropped_image)
            v_channel = pixel_array[:, :, 2]
            flat_pixels = v_channel.flatten()
            num_pixels = len(flat_pixels)
            n_top = max(1, int(num_pixels * 0.2))
            top_pixels = np.sort(flat_pixels)[-n_top:]
            score = np.mean(top_pixels)
            if score > best_score:
                best_score = score
                best_img = img
        return ImageDrawer(best_img) if best_img else None

    def __init__(self, image: Image.Image):
        self._image = image
        self._draw = ImageDraw.Draw(image)

    def when(
        self,
        flag: bool,
        fn: Callable[..., ImageDrawerPort],
        /,
        *args: object,
        **kwargs: object,
    ) -> "ImageDrawer":
        if not flag:
            return self
        result = fn(self, *args, **kwargs)
        return cast("ImageDrawer", result)

    T = TypeVar("T")

    def for_each(
        self,
        iterable: Iterable[T],
        fn: Callable[[T, ImageDrawerPort], ImageDrawerPort],
    ) -> "ImageDrawer":
        for item in iterable:
            fn(item, self)
        return self

    def save(self, path: Path) -> None:
        self._image.save(path)

    def draw_rectangle(
        self,
        rect: Tuple[int, int, int, int],
        fill_color: Color | None,
        outline_color: Color | None,
        outline_width: int,
    ) -> "ImageDrawer":
        self._draw.rectangle(
            rect,
            fill=fill_color,
            outline=outline_color,
            width=outline_width,
        )
        return self

    def draw_rounded_rectangle(
        self,
        rect: Tuple[int, int, int, int],
        radius: int,
        fill_color: Color | None,
        outline_color: Color | None,
        outline_width: int,
    ) -> ImageDrawer:
        self._draw.rounded_rectangle(
            rect,
            radius=radius,
            fill=fill_color,
            outline=outline_color,
            width=outline_width,
        )
        return self

    def draw_text(
        self,
        text: str,
        position: Tuple[int, int],
        font_name: str,
        font_size: int,
        fill_color: Color,
    ) -> ImageDrawer:
        font = ImageFont.truetype(font_name, font_size)
        self._draw.text(position, text, fill=fill_color, font=font)
        return self

    def draw_text_with_outline(
        self,
        text: str,
        position: Tuple[int, int],
        font_name: str,
        font_size: int,
        fill_color: Color,
        outline_color: Color,
        outline_width: int,
        center: bool = False,
    ) -> ImageDrawer:
        font = ImageFont.truetype(font_name, font_size)
        offsets = [
            (-outline_width, 0),
            (outline_width, 0),
            (0, -outline_width),
            (0, outline_width),
            (-outline_width, -outline_width),
            (-outline_width, outline_width),
            (outline_width, -outline_width),
            (outline_width, outline_width),
        ]

        if center:
            bbox = self._draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            position = (
                int(position[0] - text_width // 2),
                int(position[1] - text_height // 2),
            )

        for dx, dy in offsets:
            self._draw.text(
                (position[0] + dx, position[1] + dy),
                text,
                fill=outline_color,
                font=font,
            )
        self._draw.text(position, text, fill=fill_color, font=font)
        return self

    def draw_image(
        self,
        path: Path,
        position: Tuple[int, int],
        crop: Optional[Tuple[int, int, int, int]] = None,
        size: Optional[Tuple[int, int]] = None,
    ) -> "ImageDrawer":
        img = Image.open(path).convert("RGBA")
        if crop:
            img = img.crop(crop)
        if size:
            img = img.resize(size)
        self._image.paste(img, position, img)
        return self

    def overlay_image(self, path: Path) -> "ImageDrawer":
        overlay_image = Image.open(path).convert("RGBA")
        self._image = Image.alpha_composite(self._image, overlay_image)
        self._draw = ImageDraw.Draw(self._image)
        return self
