#!/usr/bin/env python3
"""ラベリングCSVからブキ追加テンプレート群を生成するCLI。"""
# ruff: noqa: E402

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_SRC = REPO_ROOT / "backend" / "src"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

from splat_replay.infrastructure.adapters.weapon_detection import (  # noqa: E402
    constants,
    labeling_variant_bank,
)

IMAGE_COLUMN_CANDIDATES = (
    "image",
    "image_path",
    "filename",
    "file_name",
    "file",
    "path",
    "画像",
)
LABEL_COLUMN_CANDIDATES = (
    "label",
    "weapon",
    "weapon_name",
    "true_label",
    "true_weapon",
    "ground_truth",
    "武器名",
    "武器",
    "ブキ",
    "正解",
)
DEFAULT_OUTPUT_DIR = (
    "backend/assets/matching/weapon/generated_labeling_variants"
)
RAW_NONE_LABEL = "None"
SELF_SCORE_PATTERN = re.compile(r"_score_([0-9]+(?:\.[0-9]+)?)", re.IGNORECASE)


class BuildError(RuntimeError):
    """追加テンプレート生成で期待外の入力を検出した場合の例外。"""


@dataclass(frozen=True)
class LabelRow:
    """ラベリングCSVの1行。"""

    row_number: int
    image_value: str
    image_path: Path
    weapon: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="ラベリングCSVからブキ追加テンプレート群を生成する。"
    )
    parser.add_argument(
        "--images-dir",
        required=True,
        help="ラベリング画像ディレクトリ。",
    )
    parser.add_argument(
        "--csv",
        required=True,
        help="画像列とラベル列を含むラベリングCSV。",
    )
    parser.add_argument(
        "--weapon",
        action="append",
        required=True,
        help="variant 化するブキ名。複数回指定可能。",
    )
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        help="生成テンプレート出力先ディレクトリ。",
    )
    return parser.parse_args()


def _resolve_existing_path(raw_path: str) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path
    from_cwd = (Path.cwd() / path).resolve()
    if from_cwd.exists():
        return from_cwd
    return (REPO_ROOT / path).resolve()


def _normalize_header_name(name: str) -> str:
    return name.strip().casefold()


def _detect_column_name(
    *, fieldnames: Sequence[str], candidates: tuple[str, ...], role: str
) -> str:
    normalized_to_original = {
        _normalize_header_name(name): name for name in fieldnames
    }
    for candidate in candidates:
        detected = normalized_to_original.get(
            _normalize_header_name(candidate)
        )
        if detected is not None:
            return detected
    raise BuildError(
        f"CSV列を特定できませんでした: {role}. "
        f"候補={list(candidates)}, 実際の列={fieldnames}"
    )


def _normalize_weapon_label(label: str) -> str:
    normalized = label.strip()
    if normalized == RAW_NONE_LABEL:
        return constants.UNKNOWN_WEAPON_LABEL
    return normalized


def _resolve_image_path(*, images_dir: Path, image_value: str) -> Path:
    path_text = image_value.strip()
    if not path_text:
        raise BuildError("画像パス列が空です。")

    candidate = Path(path_text)
    if candidate.is_absolute():
        return candidate

    normalized = path_text.replace("\\", "/")
    return (images_dir / normalized).resolve()


def _normalize_target_weapons(weapons: Iterable[str]) -> tuple[str, ...]:
    normalized: list[str] = []
    seen: set[str] = set()
    for weapon in weapons:
        value = weapon.strip()
        if not value or value in seen:
            continue
        seen.add(value)
        normalized.append(value)
    if not normalized:
        raise BuildError("--weapon は1件以上必要です。")
    return tuple(normalized)


def _load_label_rows(
    *,
    csv_path: Path,
    images_dir: Path,
    target_weapons: set[str],
) -> list[LabelRow]:
    if not csv_path.is_file():
        raise BuildError(f"CSV ファイルが見つかりません: {csv_path}")

    rows: list[LabelRow] = []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        if reader.fieldnames is None:
            raise BuildError(f"CSVヘッダーがありません: {csv_path}")

        image_column = _detect_column_name(
            fieldnames=reader.fieldnames,
            candidates=IMAGE_COLUMN_CANDIDATES,
            role="画像パス列",
        )
        label_column = _detect_column_name(
            fieldnames=reader.fieldnames,
            candidates=LABEL_COLUMN_CANDIDATES,
            role="正解ラベル列",
        )

        for row_number, row in enumerate(reader, start=2):
            image_value = str(row.get(image_column, "")).strip()
            weapon = _normalize_weapon_label(str(row.get(label_column, "")))
            if (
                not image_value
                or not weapon
                or weapon == constants.UNKNOWN_WEAPON_LABEL
                or weapon not in target_weapons
            ):
                continue
            rows.append(
                LabelRow(
                    row_number=row_number,
                    image_value=image_value,
                    image_path=_resolve_image_path(
                        images_dir=images_dir,
                        image_value=image_value,
                    ),
                    weapon=weapon,
                )
            )

    if not rows:
        raise BuildError("候補となるラベリング行がありません。")
    return rows


def _extract_self_score_from_filename(image_value: str) -> float | None:
    matched = SELF_SCORE_PATTERN.search(Path(image_value).name)
    if matched is None:
        return None
    return float(matched.group(1))


def _compute_file_hash(path: Path) -> str:
    if not path.is_file():
        raise BuildError(f"画像ファイルが見つかりません: {path}")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _asset_relative_path(*, assets_dir: Path, target_path: Path) -> str:
    try:
        relative = target_path.resolve().relative_to(assets_dir.resolve())
    except ValueError as exc:
        raise BuildError(
            "output_dir は backend/assets 配下である必要があります。 "
            f"assets_dir={assets_dir}, target_path={target_path}"
        ) from exc
    return f"assets/{relative.as_posix()}"


def build_variant_bank(
    *,
    images_dir: Path,
    csv_path: Path,
    weapons: Sequence[str],
    output_dir: Path,
    assets_dir: Path | None = None,
) -> dict[str, object]:
    normalized_weapons = _normalize_target_weapons(weapons)
    resolved_assets_dir = (
        assets_dir.resolve()
        if assets_dir is not None
        else (REPO_ROOT / "backend" / "assets").resolve()
    )
    assets_weapon_dir = resolved_assets_dir / "matching" / "weapon"

    label_rows = _load_label_rows(
        csv_path=csv_path,
        images_dir=images_dir,
        target_weapons=set(normalized_weapons),
    )

    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest_items: list[dict[str, object]] = []
    selected_rows = 0
    selected_weapons = 0
    for weapon in normalized_weapons:
        base_mask_path = assets_weapon_dir / f"{weapon}_mask.png"
        if not base_mask_path.is_file():
            raise BuildError(
                f"mask ファイルが見つかりません: {base_mask_path}"
            )

        seen_hashes: set[str] = set()
        variant_index = 0
        for row in label_rows:
            if row.weapon != weapon:
                continue
            file_hash = _compute_file_hash(row.image_path)
            if file_hash in seen_hashes:
                continue
            seen_hashes.add(file_hash)
            variant_index += 1
            selected_rows += 1

            template_filename = (
                f"{weapon}_labeling_variant_{variant_index:03d}.png"
            )
            template_output_path = output_dir / template_filename
            shutil.copy2(row.image_path, template_output_path)

            manifest_items.append(
                {
                    "weapon": weapon,
                    "template_path": _asset_relative_path(
                        assets_dir=resolved_assets_dir,
                        target_path=template_output_path,
                    ),
                    "mask_path": _asset_relative_path(
                        assets_dir=resolved_assets_dir,
                        target_path=base_mask_path,
                    ),
                    "source_image_path": str(row.image_path),
                    "self_score": _extract_self_score_from_filename(
                        row.image_value
                    ),
                }
            )

        if variant_index > 0:
            selected_weapons += 1

    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "version": labeling_variant_bank.MANIFEST_VERSION,
                "items": manifest_items,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    return {
        "total_rows": len(label_rows),
        "template_count": len(manifest_items),
        "weapon_count": selected_weapons,
        "manifest_path": str(manifest_path),
        "output_dir": str(output_dir),
        "selected_rows": selected_rows,
    }


def main() -> None:
    args = parse_args()
    summary = build_variant_bank(
        images_dir=_resolve_existing_path(args.images_dir),
        csv_path=_resolve_existing_path(args.csv),
        weapons=args.weapon,
        output_dir=_resolve_existing_path(args.output_dir),
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
