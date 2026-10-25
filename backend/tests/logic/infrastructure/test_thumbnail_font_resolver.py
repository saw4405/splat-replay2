"""フォントを使わず、画像契約と実同梱6枚を検証する。"""

from pathlib import Path
import pytest
from PIL import Image, ImageDraw
from splat_replay.infrastructure.adapters.image.thumbnail_rule_image_resolver import (
    ThumbnailRuleImageResolver,
)
from splat_replay.domain.models import Rule


def test_bundled_rule_images_are_valid_without_installed_fonts() -> None:
    root = Path(__file__).resolve().parents[3] / "assets/thumbnail/rule-labels"
    resolver = ThumbnailRuleImageResolver()
    for rule in Rule:
        path = root / f"{rule.name.lower()}.png"
        assert resolver.resolve(path) == path
        with Image.open(path) as image:
            assert image.size == (532, 135)


@pytest.mark.parametrize(
    "kind",
    ["missing", "corrupt", "rgb", "wide", "short", "empty", "black", "padded"],
)
def test_invalid_or_missing_images_fail_without_font_fallback(
    tmp_path: Path, kind: str
) -> None:
    path = tmp_path / "label.png"
    if kind == "corrupt":
        path.write_bytes(b"not png")
    elif kind != "missing":
        size = (
            (533, 135)
            if kind == "wide"
            else (532, 134)
            if kind == "short"
            else (532, 135)
        )
        image = Image.new("RGBA", size, (255, 255, 255, 0))
        draw = ImageDraw.Draw(image)
        if kind != "empty":
            draw.line(
                (0, 0, size[0] - 1, size[1] - 1),
                fill="black" if kind == "black" else "white",
                width=3,
            )
        if kind == "padded":
            image = Image.new("RGBA", size, (255, 255, 255, 0))
            ImageDraw.Draw(image).rectangle((10, 10, 500, 120), fill="white")
        if kind == "rgb":
            image = image.convert("RGB")
        image.save(path)
    assert ThumbnailRuleImageResolver().resolve(path) is None


def test_rechecks_replaced_image_without_using_a_stale_cache(
    tmp_path: Path,
) -> None:
    root = Path(__file__).resolve().parents[3] / "assets/thumbnail/rule-labels"
    path = tmp_path / "label.png"
    path.write_bytes((root / "turf_war.png").read_bytes())
    resolver = ThumbnailRuleImageResolver()
    assert resolver.resolve(path) == path
    path.write_bytes(b"corrupt replacement")
    assert resolver.resolve(path) is None
