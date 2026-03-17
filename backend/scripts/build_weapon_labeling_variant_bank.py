#!/usr/bin/env python3
"""ラベリングCSVからブキ追加テンプレート群を生成するCLI。"""
# ruff: noqa: E402

from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import cv2
import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_SRC = REPO_ROOT / "backend" / "src"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

from splat_replay.infrastructure.adapters.weapon_detection import (  # noqa: E402
    constants,
    labeling_variant_bank,
)
from splat_replay.infrastructure.matchers import TemplateMatcher  # noqa: E402
from splat_replay.infrastructure.matchers.utils import imread_unicode  # noqa: E402

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


class BuildError(RuntimeError):
    """追加テンプレート生成で期待外の入力を検出した場合の例外。"""


@dataclass(frozen=True)
class LabelRow:
    """ラベリングCSVの1行。"""

    row_number: int
    image_value: str
    image_path: Path
    weapon: str


@dataclass(frozen=True)
class CandidateRow:
    """追加テンプレート候補。"""

    row: LabelRow
    self_score: float
    image_hash: int


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
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        help="生成テンプレート出力先ディレクトリ。",
    )
    parser.add_argument(
        "--min-samples-per-weapon",
        type=int,
        default=2,
        help="候補選定を行う最低サンプル数。",
    )
    parser.add_argument(
        "--max-variants-per-weapon",
        type=int,
        default=2,
        help="各ブキにつき生成する追加テンプレート上限数。",
    )
    parser.add_argument(
        "--self-score-max",
        type=float,
        default=0.90,
        help="既存テンプレート自己一致がこの値以下の画像だけを候補にする。",
    )
    parser.add_argument(
        "--min-hash-distance",
        type=int,
        default=6,
        help="同一ブキ内で重複候補を避ける aHash ハミング距離の最小値。",
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


def _load_label_rows(*, csv_path: Path, images_dir: Path) -> list[LabelRow]:
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


def _compute_ahash(image: np.ndarray) -> int:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    resized = cv2.resize(gray, (8, 8), interpolation=cv2.INTER_AREA)
    average = float(resized.mean())
    bits = (resized >= average).astype(np.uint8).reshape(-1)
    value = 0
    for bit in bits:
        value = (value << 1) | int(bit)
    return value


def _hamming_distance(left: int, right: int) -> int:
    return int((left ^ right).bit_count())


def _load_bgr_image(path: Path) -> np.ndarray:
    image = imread_unicode(path, flags=cv2.IMREAD_COLOR)
    if image is None:
        raise BuildError(f"画像読み込みに失敗しました: {path}")
    return image


def _build_candidate_rows(
    *,
    label_rows_by_weapon: dict[str, list[LabelRow]],
    assets_weapon_dir: Path,
) -> dict[str, list[CandidateRow]]:
    result: dict[str, list[CandidateRow]] = {}
    for weapon, rows in label_rows_by_weapon.items():
        template_path = assets_weapon_dir / f"{weapon}.png"
        mask_path = assets_weapon_dir / f"{weapon}_mask.png"
        if not template_path.is_file() or not mask_path.is_file():
            continue

        matcher = TemplateMatcher(
            template_path=template_path,
            mask_path=mask_path,
            threshold=0.0,
            response_top_k=constants.TEMPLATE_RESPONSE_TOP_K,
        )
        candidates: list[CandidateRow] = []
        for row in rows:
            image = _load_bgr_image(row.image_path)
            self_score = matcher._score(image)
            candidates.append(
                CandidateRow(
                    row=row,
                    self_score=self_score,
                    image_hash=_compute_ahash(image),
                )
            )
        candidates.sort(
            key=lambda item: (item.self_score, item.row.image_value)
        )
        result[weapon] = candidates
    return result


def _select_candidates(
    *,
    candidates_by_weapon: dict[str, list[CandidateRow]],
    min_samples_per_weapon: int,
    max_variants_per_weapon: int,
    self_score_max: float,
    min_hash_distance: int,
) -> dict[str, list[CandidateRow]]:
    selected: dict[str, list[CandidateRow]] = {}
    for weapon, candidates in candidates_by_weapon.items():
        if len(candidates) < min_samples_per_weapon:
            continue
        picked: list[CandidateRow] = []
        for candidate in candidates:
            if candidate.self_score > self_score_max:
                continue
            if any(
                _hamming_distance(candidate.image_hash, item.image_hash)
                < min_hash_distance
                for item in picked
            ):
                continue
            picked.append(candidate)
            if len(picked) >= max_variants_per_weapon:
                break
        if picked:
            selected[weapon] = picked
    return selected


def _asset_relative_path(*, assets_dir: Path, target_path: Path) -> str:
    relative = target_path.resolve().relative_to(assets_dir.resolve())
    return f"assets/{relative.as_posix()}"


def _write_outputs(
    *,
    selected_candidates: dict[str, list[CandidateRow]],
    assets_dir: Path,
    assets_weapon_dir: Path,
    output_dir: Path,
) -> dict[str, object]:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest_items: list[dict[str, object]] = []
    summary_rows: list[dict[str, str | float | int]] = []
    for weapon in sorted(selected_candidates):
        mask_path = assets_weapon_dir / f"{weapon}_mask.png"
        mask_asset_path = _asset_relative_path(
            assets_dir=assets_dir,
            target_path=mask_path,
        )
        for index, candidate in enumerate(
            selected_candidates[weapon], start=1
        ):
            template_filename = f"{weapon}_variant_labeling_{index:03d}.png"
            template_output_path = output_dir / template_filename
            shutil.copy2(candidate.row.image_path, template_output_path)
            template_asset_path = _asset_relative_path(
                assets_dir=assets_dir,
                target_path=template_output_path,
            )
            manifest_items.append(
                {
                    "weapon": weapon,
                    "template_path": template_asset_path,
                    "mask_path": mask_asset_path,
                    "source_image_path": str(candidate.row.image_path),
                    "self_score": round(candidate.self_score, 6),
                }
            )
            summary_rows.append(
                {
                    "weapon": weapon,
                    "variant_index": index,
                    "image": candidate.row.image_value,
                    "self_score": round(candidate.self_score, 6),
                }
            )

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

    summary_csv_path = output_dir / "selection_summary.csv"
    with summary_csv_path.open(
        "w", encoding="utf-8-sig", newline=""
    ) as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=["weapon", "variant_index", "image", "self_score"],
        )
        writer.writeheader()
        writer.writerows(summary_rows)

    return {
        "manifest_path": str(manifest_path),
        "summary_csv_path": str(summary_csv_path),
        "template_count": len(manifest_items),
        "weapon_count": len(selected_candidates),
    }


def main() -> None:
    args = parse_args()
    images_dir = _resolve_existing_path(args.images_dir)
    csv_path = _resolve_existing_path(args.csv)
    output_dir = _resolve_existing_path(args.output_dir)
    assets_dir = (REPO_ROOT / "backend" / "assets").resolve()
    assets_weapon_dir = assets_dir / "matching" / "weapon"

    label_rows = _load_label_rows(csv_path=csv_path, images_dir=images_dir)
    grouped_rows: dict[str, list[LabelRow]] = defaultdict(list)
    for row in label_rows:
        grouped_rows[row.weapon].append(row)

    candidates_by_weapon = _build_candidate_rows(
        label_rows_by_weapon=dict(grouped_rows),
        assets_weapon_dir=assets_weapon_dir,
    )
    selected_candidates = _select_candidates(
        candidates_by_weapon=candidates_by_weapon,
        min_samples_per_weapon=args.min_samples_per_weapon,
        max_variants_per_weapon=args.max_variants_per_weapon,
        self_score_max=args.self_score_max,
        min_hash_distance=args.min_hash_distance,
    )
    summary = _write_outputs(
        selected_candidates=selected_candidates,
        assets_dir=assets_dir,
        assets_weapon_dir=assets_weapon_dir,
        output_dir=output_dir,
    )
    print(
        json.dumps(
            {
                "total_rows": len(label_rows),
                "candidate_weapon_count": len(candidates_by_weapon),
                **summary,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
