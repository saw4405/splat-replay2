from __future__ import annotations

import json
from pathlib import Path

import pytest
from splat_replay.infrastructure.adapters.weapon_detection import (
    labeling_variant_bank,
)


def test_load_labeling_variant_records_reads_valid_manifest(
    tmp_path: Path,
) -> None:
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "version": labeling_variant_bank.MANIFEST_VERSION,
                "items": [
                    {
                        "weapon": "テストブキ",
                        "template_path": "assets/matching/weapon/test.png",
                        "mask_path": "assets/matching/weapon/test_mask.png",
                        "source_image_path": "C:/tmp/test.png",
                        "self_score": 0.875,
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    records = labeling_variant_bank.load_labeling_variant_records(
        manifest_path
    )

    assert records == (
        labeling_variant_bank.LabelingVariantRecord(
            weapon="テストブキ",
            template_path="assets/matching/weapon/test.png",
            mask_path="assets/matching/weapon/test_mask.png",
            source_image_path="C:/tmp/test.png",
            self_score=0.875,
        ),
    )


def test_load_labeling_variant_records_rejects_unsupported_version(
    tmp_path: Path,
) -> None:
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps({"version": 999, "items": []}, ensure_ascii=False),
        encoding="utf-8",
    )

    with pytest.raises(
        labeling_variant_bank.LabelingVariantManifestError,
        match="未対応の manifest version",
    ):
        labeling_variant_bank.load_labeling_variant_records(manifest_path)
