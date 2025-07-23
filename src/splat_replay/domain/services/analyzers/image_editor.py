"""Image matcher port definition."""

from __future__ import annotations

from typing import Protocol, Callable

from splat_replay.domain.models import Frame


class ImageEditorPort(Protocol):
    """画像編集の技術的機能を提供するポート。"""

    @property
    def image(self) -> Frame: ...

    def rotate(self, angle: float) -> ImageEditorPort: ...

    def resize(self, scale_x: float, scale_y: float) -> ImageEditorPort: ...

    def padding(
        self,
        top: int,
        bottom: int,
        left: int,
        right: int,
        color: tuple[int, int, int] = (255, 255, 255),
    ) -> ImageEditorPort: ...

    def binarize(self) -> ImageEditorPort: ...

    def erode(
        self, kernel_size: tuple[int, int] = (2, 2), iterations: int = 1
    ) -> ImageEditorPort: ...

    def invert(self) -> ImageEditorPort: ...


ImageEditorFactory = Callable[[Frame], ImageEditorPort]
