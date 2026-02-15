"""外形モデルの読み込み・不足補完。"""

from __future__ import annotations

from math import ceil
from pathlib import Path

import cv2
import numpy as np

from . import constants
from .team_color import detect_slot_team_region


def ensure_outline_models(
    *, assets_dir: Path, logger
) -> dict[str, np.ndarray]:
    """外形モデルをロードし、不足時は入力画像から補完する。"""
    missing_species = [
        species
        for species, filename in constants.OUTLINE_MODEL_MASK_FILES.items()
        if not (assets_dir / filename).exists()
    ]
    if missing_species:
        logger.info(
            "外形モデル不足を検出、補完を開始", species=missing_species
        )
        _build_outline_models(
            assets_dir=assets_dir, species_to_build=tuple(missing_species)
        )
    return _load_model_masks(assets_dir)


def infer_species_and_mask(
    *,
    detected_mask: np.ndarray,
    model_masks: dict[str, np.ndarray],
) -> tuple[str, np.ndarray]:
    """検出マスクに最も近い種別モデルを返す。"""
    species_iter = iter(model_masks.items())
    first_species, first_model = next(species_iter)
    best_aligned, best_score = _align_model_mask_to_detected_mask(
        detected_mask=detected_mask,
        model_mask=first_model,
        max_shift=constants.OUTLINE_ALIGN_MAX_SHIFT,
    )
    best_species = first_species

    for species, model_mask in species_iter:
        aligned, score = _align_model_mask_to_detected_mask(
            detected_mask=detected_mask,
            model_mask=model_mask,
            max_shift=constants.OUTLINE_ALIGN_MAX_SHIFT,
        )
        if score > best_score:
            best_species = species
            best_aligned = aligned
            best_score = score

    return best_species, best_aligned


def _build_outline_models(
    *, assets_dir: Path, species_to_build: tuple[str, ...]
) -> None:
    for species in species_to_build:
        prefix = constants.OUTLINE_INPUT_PREFIX[species]
        input_paths = sorted(assets_dir.glob(f"{prefix}*.png"))
        if not input_paths:
            raise FileNotFoundError(
                f"外形モデル入力が見つかりません: prefix={prefix}"
            )

        masks: list[np.ndarray] = []
        for image_path in input_paths:
            image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
            if image is None:
                continue
            mask = detect_slot_team_region(image)
            if int(mask.sum()) == 0:
                continue
            masks.append(mask.astype(np.uint8))

        if not masks:
            raise ValueError(f"外形モデル入力が空です: species={species}")

        reference_index = _pick_reference_index(masks)
        reference_mask = masks[reference_index]

        aligned_masks: list[np.ndarray] = []
        for index, mask in enumerate(masks):
            if index == reference_index:
                aligned_masks.append(mask)
                continue
            _, _, aligned = _find_best_shift(
                reference_mask,
                mask,
                max_shift=constants.OUTLINE_MODEL_MAX_SHIFT,
            )
            aligned_masks.append(aligned)

        votes = np.stack(aligned_masks, axis=0).sum(axis=0)
        threshold = max(
            1, ceil(len(aligned_masks) * constants.OUTLINE_MODEL_VOTE_RATIO)
        )
        model_mask = (votes >= threshold).astype(np.uint8)
        model_mask = cv2.morphologyEx(
            model_mask, cv2.MORPH_CLOSE, np.ones((3, 3), dtype=np.uint8)
        )
        model_mask = _largest_component(model_mask)
        model_mask = _fill_holes(model_mask)

        output_path = assets_dir / constants.OUTLINE_MODEL_MASK_FILES[species]
        output_path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(output_path), model_mask * 255)


def _load_model_masks(assets_dir: Path) -> dict[str, np.ndarray]:
    model_masks: dict[str, np.ndarray] = {}
    for species, filename in constants.OUTLINE_MODEL_MASK_FILES.items():
        mask_path = assets_dir / filename
        mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
        if mask is None:
            raise FileNotFoundError(f"モデルマスク読み込み失敗: {mask_path}")
        model_masks[species] = (mask > 127).astype(np.uint8)
    return model_masks


def _pick_reference_index(masks: list[np.ndarray]) -> int:
    areas = [int(mask.sum()) for mask in masks]
    sorted_areas = sorted(areas)
    median_area = sorted_areas[len(sorted_areas) // 2]
    return min(
        range(len(areas)), key=lambda idx: abs(areas[idx] - median_area)
    )


def _align_model_mask_to_detected_mask(
    *,
    detected_mask: np.ndarray,
    model_mask: np.ndarray,
    max_shift: int,
) -> tuple[np.ndarray, float]:
    _, _, aligned = _find_best_shift(detected_mask, model_mask, max_shift)
    aligned = cv2.morphologyEx(
        aligned, cv2.MORPH_CLOSE, np.ones((3, 3), dtype=np.uint8)
    )
    aligned = _largest_component(aligned)
    aligned = _fill_holes(aligned)
    score = _iou_score(detected_mask, aligned)
    return aligned, score


def _find_best_shift(
    reference_mask: np.ndarray,
    target_mask: np.ndarray,
    max_shift: int,
) -> tuple[int, int, np.ndarray]:
    ref_x, ref_y = _mask_center(reference_mask)
    tgt_x, tgt_y = _mask_center(target_mask)
    base_dx = int(round(ref_x - tgt_x))
    base_dy = int(round(ref_y - tgt_y))

    best_dx = base_dx
    best_dy = base_dy
    best_mask = _shift_mask(target_mask, base_dx, base_dy)
    best_score = _iou_score(reference_mask, best_mask)

    for dy in range(base_dy - max_shift, base_dy + max_shift + 1):
        for dx in range(base_dx - max_shift, base_dx + max_shift + 1):
            shifted = _shift_mask(target_mask, dx, dy)
            score = _iou_score(reference_mask, shifted)
            is_better = score > best_score
            is_tie = abs(score - best_score) <= constants.SCORE_TIE_EPSILON
            is_shorter_shift = (dx * dx + dy * dy) < (
                best_dx * best_dx + best_dy * best_dy
            )
            if is_better or (is_tie and is_shorter_shift):
                best_score = score
                best_dx = dx
                best_dy = dy
                best_mask = shifted

    return best_dx, best_dy, best_mask


def _mask_center(mask: np.ndarray) -> tuple[float, float]:
    moments = cv2.moments(mask)
    if moments["m00"] <= 0:
        y_indices, x_indices = np.where(mask > 0)
        if len(x_indices) == 0:
            return (mask.shape[1] / 2.0, mask.shape[0] / 2.0)
        return (float(x_indices.mean()), float(y_indices.mean()))
    return (
        float(moments["m10"] / moments["m00"]),
        float(moments["m01"] / moments["m00"]),
    )


def _shift_mask(mask: np.ndarray, dx: int, dy: int) -> np.ndarray:
    """マスク画像をdx, dy方向にシフトする。"""
    transform = np.array(
        [[1.0, 0.0, float(dx)], [0.0, 1.0, float(dy)]], dtype=np.float32
    )
    # OpenCVの型推論は厳密だが、実行時には問題なく動作するため型チェックを無効化
    shifted = cv2.warpAffine(  # type: ignore[no-overload]
        mask,
        transform,
        (mask.shape[1], mask.shape[0]),
        flags=cv2.INTER_NEAREST,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=0,
    )
    return (shifted > 0).astype(np.uint8)


def _iou_score(mask_a: np.ndarray, mask_b: np.ndarray) -> float:
    intersection = int(np.logical_and(mask_a > 0, mask_b > 0).sum())
    union = int(np.logical_or(mask_a > 0, mask_b > 0).sum())
    if union == 0:
        return 0.0
    return intersection / float(union)


def _largest_component(mask: np.ndarray) -> np.ndarray:
    component_count, labels, stats, _ = cv2.connectedComponentsWithStats(
        mask.astype(np.uint8), connectivity=8
    )
    if component_count <= 1:
        return (mask > 0).astype(np.uint8)
    best_id = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    return (labels == best_id).astype(np.uint8)


def _fill_holes(mask: np.ndarray) -> np.ndarray:
    binary = (mask > 0).astype(np.uint8)
    inverse = (1 - binary).astype(np.uint8)
    component_count, labels, _, _ = cv2.connectedComponentsWithStats(
        inverse, connectivity=8
    )

    border_component_ids = set(np.unique(labels[0, :]))
    border_component_ids.update(np.unique(labels[-1, :]))
    border_component_ids.update(np.unique(labels[:, 0]))
    border_component_ids.update(np.unique(labels[:, -1]))

    filled = binary.copy()
    for component_id in range(1, component_count):
        if component_id in border_component_ids:
            continue
        filled[labels == component_id] = 1
    return filled.astype(np.uint8)
