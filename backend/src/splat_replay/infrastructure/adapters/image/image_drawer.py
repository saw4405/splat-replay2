from __future__ import annotations

from pathlib import Path
from typing import Callable, Iterable, List, Optional, Tuple, TypeVar, cast

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from splat_replay.application.interfaces import Color, ImageDrawerPort


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

    def __init__(self, image: Image.Image) -> None:
        self._image = image
        self._draw = ImageDraw.Draw(image)
        self._base: Image.Image | None = None
        self._element_bounds: tuple[int, int, int, int] | None = None

    def begin_element(self) -> None:
        self._element_bounds = None

    def end_element(self) -> tuple[int, int, int, int] | None:
        return self._element_bounds

    def _record_bounds(self, rect: tuple[int, int, int, int]) -> None:
        if rect[2] <= rect[0] or rect[3] <= rect[1]:
            return
        previous = self._element_bounds
        self._element_bounds = (
            rect
            if previous is None
            else (
                min(previous[0], rect[0]),
                min(previous[1], rect[1]),
                max(previous[2], rect[2]),
                max(previous[3], rect[3]),
            )
        )

    def begin_layer(self) -> None:
        self._base = self._image
        self._image = Image.new("RGBA", self._base.size)
        self._draw = ImageDraw.Draw(self._image)

    def end_layer(self, opacity: float) -> None:
        if self._base is None:
            raise RuntimeError("描画レイヤーがありません")
        alpha = self._image.getchannel("A").point(lambda a: round(a * opacity))
        self._image.putalpha(alpha)
        mode = self._base.mode
        self._image = Image.alpha_composite(
            self._base.convert("RGBA"), self._image
        ).convert(mode)
        self._base = None
        self._draw = ImageDraw.Draw(self._image)

    def fit_background(self, x: int, y: int, scale: float) -> None:
        factor = (
            max(1920 / self._image.width, 1080 / self._image.height) * scale
        )
        left = (1920 - self._image.width * factor) / 2 + x
        top = (1080 - self._image.height * factor) / 2 + y
        # 細長い素材でも巨大な拡大画像を確保せず、出力範囲だけを描画する。
        self._image = self._image.transform(
            (1920, 1080),
            Image.Transform.AFFINE,
            (1 / factor, 0, -left / factor, 0, 1 / factor, -top / factor),
            resample=Image.Resampling.BICUBIC,
        ).convert("RGB")
        self._draw = ImageDraw.Draw(self._image)

    def draw_ellipse(
        self,
        rect: Tuple[int, int, int, int],
        fill_color: Color | None,
        outline_color: Color | None,
        outline_width: int,
    ) -> "ImageDrawer":
        self._draw.ellipse(
            rect, fill=fill_color, outline=outline_color, width=outline_width
        )
        self._record_bounds((rect[0], rect[1], rect[2] + 1, rect[3] + 1))
        return self

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
        self._record_bounds((rect[0], rect[1], rect[2] + 1, rect[3] + 1))
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
        self._record_bounds((rect[0], rect[1], rect[2] + 1, rect[3] + 1))
        return self

    def _text_bounds(
        self,
        position: tuple[int, int],
        text: str,
        font: ImageFont.FreeTypeFont,
    ) -> tuple[int, int, int, int] | None:
        # フォントの送り幅ではなく、実際に描画される字形の境界を返す。
        left, top, right, bottom = self._draw.textbbox(
            position, text, font=font
        )
        if right <= left or bottom <= top:
            return None
        mask = Image.new("L", (right - left, bottom - top))
        ImageDraw.Draw(mask).text(
            (position[0] - left, position[1] - top), text, fill=255, font=font
        )
        box = mask.getbbox()
        return (
            (left + box[0], top + box[1], left + box[2], top + box[3])
            if box is not None
            else None
        )

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
        box = self._text_bounds(position, text, font)
        if box is not None:
            self._record_bounds(box)
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
        box = self._text_bounds(position, text, font)
        if box is not None:
            self._record_bounds(
                (
                    box[0] - outline_width,
                    box[1] - outline_width,
                    box[2] + outline_width,
                    box[3] + outline_width,
                )
            )
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
        self._record_bounds(
            (
                position[0],
                position[1],
                position[0] + img.width,
                position[1] + img.height,
            )
        )
        if self._base is not None:
            self._image.alpha_composite(img, position)
        else:
            self._image.paste(img, position, img)
        return self

    def overlay_image(self, path: Path) -> "ImageDrawer":
        overlay_image = Image.open(path).convert("RGBA")
        self._image = Image.alpha_composite(self._image, overlay_image)
        self._draw = ImageDraw.Draw(self._image)
        return self
