from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "sync_weapon_templates.py"
)
MODULE_NAME = "sync_weapon_templates_for_test"
SPEC = importlib.util.spec_from_file_location(MODULE_NAME, SCRIPT_PATH)
assert SPEC is not None
assert SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[MODULE_NAME] = MODULE
SPEC.loader.exec_module(MODULE)


def test_collect_assets_allows_variant_to_reuse_base_mask(
    tmp_path: Path,
) -> None:
    (tmp_path / "パブロ・ヒュー_variant_001.png").write_bytes(b"template")
    (tmp_path / "パブロ・ヒュー_mask.png").write_bytes(b"mask")

    assets = MODULE._collect_assets(tmp_path)

    assert assets == [
        MODULE.WeaponAsset(
            template_name="パブロ・ヒュー_variant_001",
            weapon_name="パブロ・ヒュー",
            mask_name="パブロ・ヒュー",
        )
    ]


def test_collect_assets_raises_when_variant_has_no_mask_fallback(
    tmp_path: Path,
) -> None:
    (tmp_path / "パブロ・ヒュー_variant_001.png").write_bytes(b"template")

    with pytest.raises(MODULE.SyncError) as exc_info:
        MODULE._collect_assets(tmp_path)

    assert "<base>_mask.png for variants" in str(exc_info.value)


def test_build_definition_block_lines_uses_canonical_name_and_base_mask_for_variant() -> (
    None
):
    additions = [
        MODULE.PlannedAddition(
            key="weapon_template_999",
            weapon_name="パブロ・ヒュー",
            template_name="パブロ・ヒュー_variant_001",
            mask_name="パブロ・ヒュー",
        )
    ]

    lines = MODULE._build_definition_block_lines(
        additions=additions,
        threshold=0.785,
        newline="\n",
    )
    block = "".join(lines)

    assert 'name: "パブロ・ヒュー"\n' in block
    assert (
        'template_path: "assets/matching/weapon/パブロ・ヒュー_variant_001.png"\n'
        in block
    )
    assert (
        'mask_path: "assets/matching/weapon/パブロ・ヒュー_mask.png"\n'
        in block
    )
