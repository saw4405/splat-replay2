from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "build_weapon_labeling_variant_bank.py"
)


def _load_script_module():
    assert SCRIPT_PATH.is_file(), f"script missing: {SCRIPT_PATH}"
    spec = importlib.util.spec_from_file_location(
        "build_weapon_labeling_variant_bank",
        SCRIPT_PATH,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_rgba_image(path: Path, value: int) -> None:
    image = np.full((100, 90, 4), value, dtype=np.uint8)
    image[..., 3] = 255
    ok, encoded = cv2.imencode(".png", image)
    assert ok
    path.write_bytes(encoded.tobytes())


def _write_mask(path: Path) -> None:
    mask = np.zeros((100, 90), dtype=np.uint8)
    mask[10:90, 10:80] = 255
    ok, encoded = cv2.imencode(".png", mask)
    assert ok
    path.write_bytes(encoded.tobytes())


def test_build_variant_bank_generates_manifest_for_target_weapons_only(
    tmp_path: Path,
) -> None:
    module = _load_script_module()

    assets_dir = tmp_path / "backend" / "assets"
    assets_weapon_dir = assets_dir / "matching" / "weapon"
    assets_weapon_dir.mkdir(parents=True)
    images_dir = tmp_path / "images"
    images_dir.mkdir()

    for weapon in (
        "ジェットスイーパーカスタム",
        "デュアルスイーパーカスタム",
        "わかばシューター",
    ):
        _write_rgba_image(assets_weapon_dir / f"{weapon}.png", value=64)
        _write_mask(assets_weapon_dir / f"{weapon}_mask.png")

    jet_source = images_dir / "ジェットスイーパーカスタム_score_0.7274.png"
    _write_rgba_image(jet_source, value=80)
    shutil.copy2(
        jet_source,
        images_dir / "ジェットスイーパーカスタム_dup.png",
    )
    dual_source = images_dir / "デュアルスイーパーカスタム_dup1.png"
    _write_rgba_image(dual_source, value=112)
    ignored_source = images_dir / "わかばシューター_score_0.9999.png"
    _write_rgba_image(ignored_source, value=144)

    csv_path = images_dir / "labeling_weapons.csv"
    csv_path.write_text(
        "\n".join(
            [
                "filename,label",
                "ジェットスイーパーカスタム_score_0.7274.png,"
                "ジェットスイーパーカスタム",
                "ジェットスイーパーカスタム_dup.png,"
                "ジェットスイーパーカスタム",
                "デュアルスイーパーカスタム_dup1.png,"
                "デュアルスイーパーカスタム",
                "わかばシューター_score_0.9999.png,わかばシューター",
            ]
        )
        + "\n",
        encoding="utf-8-sig",
    )

    output_dir = assets_weapon_dir / "generated_labeling_variants"

    summary = module.build_variant_bank(
        images_dir=images_dir,
        csv_path=csv_path,
        weapons=(
            "ジェットスイーパーカスタム",
            "デュアルスイーパーカスタム",
        ),
        output_dir=output_dir,
        assets_dir=assets_dir,
    )

    assert summary["template_count"] == 2
    assert summary["weapon_count"] == 2

    manifest_path = output_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["version"] == 1
    assert [item["weapon"] for item in manifest["items"]] == [
        "ジェットスイーパーカスタム",
        "デュアルスイーパーカスタム",
    ]

    jet_item, dual_item = manifest["items"]
    assert jet_item["mask_path"] == (
        "assets/matching/weapon/ジェットスイーパーカスタム_mask.png"
    )
    assert jet_item["source_image_path"] == str(jet_source)
    assert jet_item["self_score"] == pytest.approx(0.7274)
    assert dual_item["mask_path"] == (
        "assets/matching/weapon/デュアルスイーパーカスタム_mask.png"
    )
    assert dual_item["source_image_path"] == str(dual_source)
    assert dual_item["self_score"] is None

    for item in manifest["items"]:
        generated = assets_dir / Path(item["template_path"]).relative_to(
            "assets"
        )
        assert generated.is_file()
