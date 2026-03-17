"""ラベリング由来の追加テンプレートマニフェストを扱う。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


MANIFEST_VERSION = 1


class LabelingVariantManifestError(RuntimeError):
    """追加テンプレートマニフェストの形式不正。"""


@dataclass(frozen=True)
class LabelingVariantRecord:
    """ラベリングCSVから生成した追加テンプレート定義。"""

    weapon: str
    template_path: str
    mask_path: str
    source_image_path: str | None = None
    self_score: float | None = None


def load_labeling_variant_records(
    manifest_path: Path,
) -> tuple[LabelingVariantRecord, ...]:
    """manifest.json から追加テンプレート定義を読み込む。"""
    if not manifest_path.is_file():
        return ()

    try:
        loaded = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise LabelingVariantManifestError(
            f"JSON の読み込みに失敗しました: {manifest_path}"
        ) from exc

    if not isinstance(loaded, dict):
        raise LabelingVariantManifestError(
            f"manifest の形式が不正です: {manifest_path}"
        )

    version = loaded.get("version")
    if version != MANIFEST_VERSION:
        raise LabelingVariantManifestError(
            "未対応の manifest version です。"
            f" expected={MANIFEST_VERSION}, actual={version}"
        )

    raw_items = loaded.get("items")
    if not isinstance(raw_items, list):
        raise LabelingVariantManifestError(
            f"items が配列ではありません: {manifest_path}"
        )

    records: list[LabelingVariantRecord] = []
    for index, raw_item in enumerate(raw_items, start=1):
        if not isinstance(raw_item, dict):
            raise LabelingVariantManifestError(
                f"items[{index}] の形式が不正です: {manifest_path}"
            )
        weapon = raw_item.get("weapon")
        template_path = raw_item.get("template_path")
        mask_path = raw_item.get("mask_path")
        source_image_path = raw_item.get("source_image_path")
        self_score = raw_item.get("self_score")
        if not isinstance(weapon, str) or not weapon.strip():
            raise LabelingVariantManifestError(
                f"items[{index}].weapon が不正です: {manifest_path}"
            )
        if not isinstance(template_path, str) or not template_path.strip():
            raise LabelingVariantManifestError(
                f"items[{index}].template_path が不正です: {manifest_path}"
            )
        if not isinstance(mask_path, str) or not mask_path.strip():
            raise LabelingVariantManifestError(
                f"items[{index}].mask_path が不正です: {manifest_path}"
            )
        if source_image_path is not None and not isinstance(
            source_image_path, str
        ):
            raise LabelingVariantManifestError(
                f"items[{index}].source_image_path が不正です: {manifest_path}"
            )
        if self_score is not None and not isinstance(self_score, int | float):
            raise LabelingVariantManifestError(
                f"items[{index}].self_score が不正です: {manifest_path}"
            )
        records.append(
            LabelingVariantRecord(
                weapon=weapon.strip(),
                template_path=template_path.strip(),
                mask_path=mask_path.strip(),
                source_image_path=(
                    source_image_path.strip()
                    if isinstance(source_image_path, str)
                    else None
                ),
                self_score=(
                    float(self_score)
                    if isinstance(self_score, int | float)
                    else None
                ),
            )
        )

    return tuple(records)
