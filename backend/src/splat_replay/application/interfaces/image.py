"""Image processing ports (editing, drawing, OCR, matching, subtitle)."""

from __future__ import annotations

from pathlib import Path
from typing import (
    Callable,
    Iterable,
    List,
    Optional,
    Protocol,
    Tuple,
    TypeVar,
    Union,
)

# Type aliases
T = TypeVar("T")
Color = Union[str, Tuple[int, ...]]


class ImageDrawerPort(Protocol):
    """画像描画処理を提供するポート。"""

    @staticmethod
    def select_brightest_image(
        paths: List[Path], target_rect: Tuple[float, float, float, float]
    ) -> Optional["ImageDrawerPort"]:
        """Select brightest image from list based on target rectangle."""
        ...

    def when(
        self,
        flag: bool,
        fn: Callable[..., "ImageDrawerPort"],
        /,
        *args: object,
        **kwargs: object,
    ) -> "ImageDrawerPort":
        """Conditionally apply drawing function."""
        ...

    def for_each(
        self,
        iterable: Iterable[T],
        fn: Callable[[T, "ImageDrawerPort"], "ImageDrawerPort"],
    ) -> "ImageDrawerPort":
        """Apply drawing function for each item."""
        ...

    def save(self, path: Path) -> None:
        """Save image to file."""
        ...

    def draw_rectangle(
        self,
        rect: Tuple[int, int, int, int],
        fill_color: Color | None,
        outline_color: Color | None,
        outline_width: int,
    ) -> "ImageDrawerPort":
        """Draw rectangle on image."""
        ...

    def draw_rounded_rectangle(
        self,
        rect: Tuple[int, int, int, int],
        radius: int,
        fill_color: Color | None,
        outline_color: Color | None,
        outline_width: int,
    ) -> "ImageDrawerPort":
        """Draw rounded rectangle on image."""
        ...

    def draw_text(
        self,
        text: str,
        position: Tuple[int, int],
        font_name: str,
        font_size: int,
        fill_color: Color,
    ) -> "ImageDrawerPort":
        """Draw text on image."""
        ...

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
    ) -> "ImageDrawerPort":
        """Draw text with outline on image."""
        ...

    def draw_image(
        self,
        path: Path,
        position: Tuple[int, int],
        crop: Optional[Tuple[int, int, int, int]] = None,
        size: Optional[Tuple[int, int]] = None,
    ) -> "ImageDrawerPort":
        """Draw image on image."""
        ...

    def overlay_image(self, path: Path) -> "ImageDrawerPort":
        """Overlay image on current image."""
        ...


# Image selector function type
ImageSelector = Callable[
    [List[Path], Tuple[float, float, float, float]], ImageDrawerPort
]


class ImageEditorPort(Protocol):
    """画像編集処理を提供するポート。"""

    # Add methods as needed
    pass


class SubtitleEditorPort(Protocol):
    """字幕編集処理を提供するポート。"""

    def merge(self, subtitles: List[Path], video_length: List[float]) -> str:
        """Merge multiple subtitle files."""
        ...


# ImageMatcherPort と OCRPort は domain.services 層に移動しました。
# Domain Service用ポートはDomain層に配置するというルールに準拠しています。
# 使用する場合は from splat_replay.domain.services import ImageMatcherPort, OCRPort
