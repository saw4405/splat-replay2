"""デザイン移行の画素再現と素材・設定の整合性を守る。"""

from dataclasses import replace
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image, ImageChops, ImageDraw
from pydantic import ValidationError
import structlog

from splat_replay.application.services.editing.thumbnail_generator import (
    ThumbnailGenerator,
)
from splat_replay.application.services.editing.thumbnail_design_service import (
    ThumbnailDesignService,
)
from splat_replay.domain.models import (
    BattleResult,
    Judgement,
    Match,
    RecordingMetadata,
    Rule,
    Stage,
    VideoAsset,
    XP,
)

from splat_replay.domain.config.video_edit import (
    ThumbnailDesign,
    ThumbnailElement,
)
from splat_replay.infrastructure.adapters.image.image_drawer import ImageDrawer
from splat_replay.infrastructure.adapters.image.thumbnail_assets import (
    ThumbnailAssets,
)
from splat_replay.infrastructure.adapters.image.thumbnail_rule_image_resolver import (
    ThumbnailRuleImageResolver,
)
from splat_replay.infrastructure.adapters.storage.settings_repository import (
    TomlSettingsRepository,
)
from splat_replay.infrastructure.adapters.system.cross_cutting import (
    FileSystemPathsAdapter,
    LocalFileSystemAdapter,
)
from splat_replay.infrastructure.config import load_settings_from_toml


def service_for(tmp_path: Path) -> ThumbnailDesignService:
    assets = ThumbnailAssets(tmp_path / "assets", tmp_path / "settings.toml")
    generator = ThumbnailGenerator(
        structlog.get_logger(),
        FileSystemPathsAdapter(),
        ImageDrawer.select_brightest_image,
        LocalFileSystemAdapter(),
        ThumbnailRuleImageResolver(),
        assets,
    )
    return ThumbnailDesignService(assets, generator)


def test_preview_uses_real_result_and_actual_highlight_crops(
    tmp_path: Path,
) -> None:
    service = service_for(tmp_path)
    source = Image.open(
        Path(__file__).parents[2] / "fixtures/templates/battle_result_9.png"
    ).convert("RGB")
    with service.assets.sample("x") as samples:
        assert samples[0].thumbnail is not None
        sample = Image.open(samples[0].thumbnail).convert("RGB")
        assert (
            sample.crop((0, 0, 750, 1080)).tobytes()
            == source.crop((0, 0, 750, 1080)).tobytes()
        )
    content, layout = service.preview_with_layout(
        service.default_design(), "x"
    )
    image = Image.open(BytesIO(content)).convert("RGB")
    expected = (
        source.crop((1467, 259, 1661, 319))
        .convert("RGBA")
        .resize((292, 120))
        .convert("RGB")
    )
    assert (
        image.crop((3, 623, 289, 737)).tobytes()
        == expected.crop((3, 3, 289, 117)).tobytes()
    )
    assert layout["highlights"] == {
        "x": 0,
        "y": 620,
        "width": 293,
        "height": 421,
    }


def test_result_background_transform_keeps_elements_in_canvas_coordinates(
    tmp_path: Path,
) -> None:
    service = service_for(tmp_path)
    design = service.default_design()
    design.elements = []
    original = Image.open(BytesIO(service.preview(design, "x"))).convert("RGB")
    design.background.x = 120
    moved = Image.open(BytesIO(service.preview(design, "x"))).convert("RGB")
    assert (
        moved.crop((120, 0, 1920, 1080)).tobytes()
        == original.crop((0, 0, 1800, 1080)).tobytes()
    )
    assert moved.crop((0, 0, 120, 1080)).getbbox() is None
    design.background.scale = 2
    design.elements = [
        ThumbnailElement(
            id="fixed",
            name="固定図形",
            source="shape",
            x=500,
            y=300,
            width=20,
            height=20,
            color="#ff0000",
            outline_width=0,
        )
    ]
    scaled = Image.open(BytesIO(service.preview(design, "x"))).convert("RGB")
    assert scaled.size == (1920, 1080)
    assert scaled.getpixel((510, 310)) == (255, 0, 0)
    assert ImageChops.difference(scaled, moved).getbbox() is not None


def test_text_bounds_follow_the_rendered_glyphs_and_missing_rate(
    tmp_path: Path,
) -> None:
    service = service_for(tmp_path)
    design = service.default_design()
    design.elements = [design.elements[0]]
    design.background.source = "image"
    image = BytesIO()
    background = Image.new("RGB", (1920, 1080), (40, 50, 60))
    background.save(image, "PNG")
    design.background.asset = service.upload(image.getvalue())
    content, layout = service.preview_with_layout(design, "x")
    rendered = Image.open(BytesIO(content)).convert("RGB")
    box = ImageChops.difference(rendered, background).getbbox()
    assert box is not None
    bounds = layout["win-lose"]
    # 縁取りを含めた描画画素と選択枠が一致し、文字列長の推定による余白はない。
    assert box[0] == bounds["x"]
    assert box[2] == bounds["x"] + bounds["width"]
    assert bounds["width"] < 400
    _, empty_layout = service.preview_with_layout(
        service.default_design(), "regular"
    )
    assert "rate" not in empty_layout


@pytest.mark.parametrize(
    "scenario", ["x", "event", "regular", "anarchy", "single"]
)
def test_default_design_matches_legacy_pixels(
    tmp_path: Path, scenario: str
) -> None:
    service = service_for(tmp_path)
    samples = legacy_samples(tmp_path, scenario)
    output = service.generator.create(samples, service.default_design())
    assert output is not None
    generated = Image.open(output).convert("RGB")
    # 設定化前の実装で同じ固定サンプルを描画した画像。新レンダラから更新しない。
    reference = Image.open(
        Path(__file__).parents[2]
        / "fixtures/thumbnail_design"
        / f"{scenario}.png"
    ).convert("RGB")
    assert generated.size == reference.size
    assert ImageChops.difference(generated, reference).getbbox() is None


@pytest.mark.parametrize(
    "template",
    ["{UNKNOWN}", "{WIN.__class__}", "{WIN!r}", "{WIN:999999}", "{WIN"],
)
def test_invalid_templates_are_rejected(template: str) -> None:
    with pytest.raises(ValidationError):
        ThumbnailElement(
            id="text", name="文字", source="text", template=template
        )


def test_saved_design_roundtrip_and_referenced_asset_deletion(
    tmp_path: Path,
) -> None:
    service = service_for(tmp_path)
    image = BytesIO()
    Image.new("RGB", (600, 300), (255, 0, 0)).save(image, "PNG")
    asset_id = service.upload(image.getvalue())
    design = service.default_design()
    design.background.source = "image"
    design.background.asset = asset_id
    repo = TomlSettingsRepository(
        tmp_path / "settings.toml", thumbnail_assets=service.assets
    )
    repo.update_sections(
        [{"id": "video_edit", "values": {"thumbnail_design": design.dict()}}]
    )
    assert (
        load_settings_from_toml(
            tmp_path / "settings.toml"
        ).video_edit.thumbnail_design
        == design
    )
    assert "{WIN} - {LOSE}" in (tmp_path / "settings.toml").read_text()
    with pytest.raises(ValueError, match="使用中"):
        service.delete(asset_id, service.default_design())
    repo.update_sections(
        [
            {
                "id": "video_edit",
                "values": {
                    "thumbnail_design": service.default_design().dict()
                },
            }
        ]
    )
    with service.assets.lease(design):
        with pytest.raises(ValueError, match="使用中"):
            service.delete(asset_id, service.default_design())
    # leaseのfinallyで保護が解除される。
    with pytest.raises(ValueError, match="使用中"):
        service.delete(asset_id, design)
    service.delete(asset_id, service.default_design())
    assert not service.assets.path(asset_id).exists()
    with pytest.raises(ValueError, match="素材が見つかりません"):
        repo.update_sections(
            [
                {
                    "id": "video_edit",
                    "values": {"thumbnail_design": design.dict()},
                }
            ]
        )
    assert (
        load_settings_from_toml(
            tmp_path / "settings.toml"
        ).video_edit.thumbnail_design
        == service.default_design()
    )


def test_shape_opacity_order_background_and_missing_rate(
    tmp_path: Path,
) -> None:
    service = service_for(tmp_path)
    image = BytesIO()
    Image.new("RGB", (600, 300), (0, 0, 200)).save(image, "PNG")
    asset_id = service.upload(image.getvalue())
    design = ThumbnailDesign.parse_obj(
        {
            "background": {"source": "image", "asset": asset_id},
            "elements": [
                {
                    "id": "shape",
                    "name": "図形",
                    "source": "shape",
                    "shape": "ellipse",
                    "width": 100,
                    "height": 100,
                    "color": "#c80000",
                    "opacity": 0.5,
                },
                {
                    "id": "rate",
                    "name": "レート",
                    "source": "rate",
                    "template": "{RATE_LABEL}{RATE_VALUE}",
                },
            ],
        }
    )
    result = Image.open(BytesIO(service.preview(design, "regular")))
    assert result.size == (1920, 1080)
    assert result.getpixel((50, 50)) == (100, 0, 100)
    assert result.getpixel((200, 200)) == (0, 0, 200)
    # カスタム文字でレートが欠けても残りの文言を描画できる。
    design.elements.append(
        ThumbnailElement(
            id="text",
            name="文字",
            source="text",
            template="Wins {WIN} {RATE}",
            x=300,
            y=300,
        )
    )
    assert service.preview(design, "regular")


def test_missing_dynamic_data_is_omitted(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    with service.assets.sample("x") as samples:
        sample = samples[0]
        assert (
            sample.metadata is not None and sample.metadata.result is not None
        )
        sample = replace(
            sample,
            metadata=replace(
                sample.metadata,
                rate=None,
                result=replace(sample.metadata.result, stage=None, kill=0),
            ),
        )
        assert service.generator.create([sample]) is not None


def test_asset_id_and_duplicate_elements_are_rejected(tmp_path: Path) -> None:
    service = service_for(tmp_path)
    for asset_id in (
        "../settings.toml",
        "/etc/passwd",
        "uploads/../../x",
        "uploads\\image.png",
    ):
        with pytest.raises(ValueError):
            service.assets.path(asset_id)
    design = service.default_design().dict()
    design["elements"].append(design["elements"][0])
    with pytest.raises(ValidationError, match="重複"):
        ThumbnailDesign.parse_obj(design)
    with pytest.raises(ValueError, match="同梱"):
        service.delete("Xマッチ.png", service.default_design())


def test_thin_background_uses_fixed_canvas_without_enormous_intermediate(
    tmp_path: Path,
) -> None:
    service = service_for(tmp_path)
    image = BytesIO()
    Image.new("RGB", (10000, 1), (10, 20, 30)).save(image, "PNG")
    asset_id = service.upload(image.getvalue())
    design = ThumbnailDesign.parse_obj(
        {"background": {"source": "image", "asset": asset_id}, "elements": []}
    )
    output = Image.open(BytesIO(service.preview(design, "single")))
    assert output.size == (1920, 1080)
    assert output.getpixel((960, 540)) == (10, 20, 30)


def legacy_samples(root: Path, scenario: str) -> list[VideoAsset]:
    image = Image.new("RGB", (1920, 1080), (36, 45, 57))
    draw = ImageDraw.Draw(image)
    draw.polygon(
        [(40, 180), (680, 100), (730, 1000), (100, 1020)],
        fill=(90, 160, 115),
    )
    for i in range(4):
        draw.rounded_rectangle(
            (780, 110 + i * 180, 1880, 260 + i * 180),
            radius=20,
            fill=(70 + i * 12, 76, 82),
        )
    draw.text((70, 500), "SAMPLE RESULT", fill=(255, 255, 255), font_size=65)
    image_path = root / "sample.png"
    image.save(image_path)
    match = {
        "event": Match.CHALLENGE,
        "regular": Match.REGULAR,
        "anarchy": Match.ANARCHY,
    }.get(scenario, Match.X)
    assets: list[VideoAsset] = []
    for i in range(1 if scenario == "single" else 7):
        frame = image.copy()
        ImageDraw.Draw(frame).text(
            (1470, 270),
            f"{15 + i}   3   4",
            fill=(255, 255, 255),
            font_size=35,
        )
        image_path = root / f"sample-{i}.png"
        frame.save(image_path)
        assets.append(
            VideoAsset(
                video=root / f"sample-{i}.mp4",
                thumbnail=image_path,
                metadata=RecordingMetadata(
                    judgement=Judgement.WIN if i < 4 else Judgement.LOSE,
                    rate=None
                    if scenario == "regular"
                    else XP(2000.0 + i * 10.1),
                    result=BattleResult(
                        match=match,
                        rule=Rule.RAINMAKER,
                        stage=Stage.HAMMERHEAD_BRIDGE
                        if i % 2 == 0
                        else Stage.SCORCH_GORGE,
                        kill=15 + i,
                        death=3,
                        special=4,
                    ),
                ),
            )
        )
    return assets
