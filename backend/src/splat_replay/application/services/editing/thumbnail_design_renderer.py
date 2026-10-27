"""解決済みの情報をデザインに従って描画する。実生成と見本表示で共用する。"""

from dataclasses import dataclass
from pathlib import Path

from splat_replay.application.interfaces import (
    FileSystemPort,
    ImageDrawerPort,
    PathsPort,
)
from splat_replay.application.interfaces.thumbnail_design import (
    ThumbnailAssetsPort,
    ThumbnailBounds,
)
from splat_replay.domain.config.video_edit import (
    ThumbnailDesign,
    ThumbnailElement,
)


@dataclass(frozen=True)
class ThumbnailContent:
    values: dict[str, str | int]
    images: dict[str, list[Path]]
    rate_color: str


def render_design(
    drawer: ImageDrawerPort,
    design: ThumbnailDesign,
    content: ThumbnailContent,
    paths: PathsPort,
    assets: ThumbnailAssetsPort | None,
    files: FileSystemPort,
    layout: dict[str, ThumbnailBounds] | None = None,
) -> None:
    for element in design.elements:
        if not element.visible or element.opacity == 0:
            continue
        if layout is not None:
            drawer.begin_element()
        if element.opacity != 1:
            drawer.begin_layer()
        _render_element(drawer, element, content, paths, assets, files)
        if element.opacity != 1:
            drawer.end_layer(element.opacity)
        if layout is not None:
            box = drawer.end_element()
            if box is not None:
                layout[element.id] = ThumbnailBounds(
                    x=box[0],
                    y=box[1],
                    width=box[2] - box[0],
                    height=box[3] - box[1],
                )


def _render_element(
    drawer: ImageDrawerPort,
    e: ThumbnailElement,
    content: ThumbnailContent,
    paths: PathsPort,
    assets: ThumbnailAssetsPort | None,
    files: FileSystemPort,
) -> None:
    position = (e.x, e.y)
    if e.source in ("win_lose", "rate", "text"):
        if e.source == "rate" and not content.values["RATE"]:
            return
        text = e.template.format_map(content.values)
        font = str(
            assets.path(e.font)
            if assets
            else paths.get_thumbnail_asset(e.font)
        )
        color = (
            content.rate_color
            if e.source == "rate" and e.auto_color
            else e.color
        )
        if e.outline_width or e.center:
            drawer.draw_text_with_outline(
                text,
                position,
                font,
                e.font_size,
                fill_color=color,
                outline_color=e.outline_color,
                outline_width=e.outline_width,
                center=e.center,
            )
        else:
            drawer.draw_text(
                text, position, font, e.font_size, fill_color=color
            )
    elif e.source == "shape":
        rect = (e.x, e.y, e.x + e.width, e.y + e.height)
        if e.shape == "ellipse":
            drawer.draw_ellipse(
                rect, e.color, e.outline_color, e.outline_width
            )
        elif e.shape == "rounded_rectangle":
            drawer.draw_rounded_rectangle(
                rect, e.radius, e.color, e.outline_color, e.outline_width
            )
        else:
            drawer.draw_rectangle(
                rect, e.color, e.outline_color, e.outline_width
            )
    elif e.source == "stages":
        sx, sy = (e.width or 960) / 960, (e.height or 348) / 348
        for i, path in enumerate(content.images.get("stages", [])):
            drawer.draw_image(
                path,
                (e.x, e.y + round(i * 180 * sy)),
                size=(max(1, round(960 * sx)), max(1, round(168 * sy))),
            )
    elif e.source == "highlights":
        sx, sy = (e.width or 292) / 292, (e.height or 420) / 420
        images = content.images.get("highlights", [])
        for i, path in enumerate(images):
            drawer.draw_image(
                path,
                (e.x, e.y + round(i * 150 * sy)),
                crop=(1467, 259, 1661, 319),
                size=(max(1, round(292 * sx)), max(1, round(120 * sy))),
            )
        for i, _ in enumerate(images):
            y = e.y + round(i * 150 * sy)
            drawer.draw_rectangle(
                (e.x, y, e.x + round(292 * sx), y + round(120 * sy)),
                None,
                e.outline_color,
                e.outline_width,
            )
    else:
        if e.source in ("image", "overlay"):
            if not e.asset:
                return
            path = (
                assets.path(e.asset)
                if assets
                else paths.get_thumbnail_asset(e.asset)
            )
            images = [path] if files.is_file(path) else []
        else:
            images = content.images.get(e.source, [])
        for path in images:
            drawer.draw_image(
                path,
                position,
                size=(e.width, e.height) if e.width and e.height else None,
            )
