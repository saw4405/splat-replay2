#!/usr/bin/env python3
"""ラベリングCSVを用いた単一スロット画像のブキ判別評価CLI。"""
# ruff: noqa: E402

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import cv2
import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_SRC = REPO_ROOT / "backend" / "src"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

from splat_replay.application.interfaces.weapon_detection import (
    WeaponCandidateScore,
)
from splat_replay.domain.config import ImageMatchingSettings
from splat_replay.infrastructure.adapters.weapon_detection import constants
from splat_replay.infrastructure.adapters.weapon_detection.recognizer import (
    WeaponRecognitionAdapter,
)
from splat_replay.infrastructure.matchers.utils import imread_unicode

DEFAULT_CONFIG_PATH = "backend/config/image_matching.yaml"
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
RAW_NONE_LABEL = "None"


class EvaluationError(RuntimeError):
    """評価処理で期待外の入力を検出した場合の例外。"""


@dataclass(frozen=True)
class LabelRow:
    """ラベリングCSVの1行。"""

    row_number: int
    image_value: str
    image_path: Path
    true_weapon: str


@dataclass(frozen=True)
class PredictionRow:
    """1画像分の推論結果。"""

    row_number: int
    image_value: str
    image_path: Path
    true_weapon: str
    predicted_weapon: str | None
    is_unmatched: bool | None
    best_score: float | None
    threshold: float | None
    top_candidates: tuple[WeaponCandidateScore, ...]
    error: str | None


class _NullLogger:
    """構造化ログ用のダミーロガー。"""

    def debug(self, event: str, **kw: object) -> None:
        return None

    def info(self, event: str, **kw: object) -> None:
        return None

    def warning(self, event: str, **kw: object) -> None:
        return None

    def error(self, event: str, **kw: object) -> None:
        return None

    def exception(self, event: str, **kw: object) -> None:
        return None


def _normalize_true_weapon_label(label: str) -> str:
    normalized = label.strip()
    if normalized == RAW_NONE_LABEL:
        return constants.UNKNOWN_WEAPON_LABEL
    return normalized


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="ブキラベリングCSVで単一スロット判別精度を評価する。"
    )
    parser.add_argument(
        "--images-dir",
        required=True,
        help="評価画像ディレクトリ。CSVの画像パスはこの配下を基準に解決。",
    )
    parser.add_argument(
        "--csv",
        required=True,
        help="画像パス列と正解ラベル列を含むラベリングCSV。",
    )
    parser.add_argument(
        "--config",
        default=DEFAULT_CONFIG_PATH,
        help="image_matching.yaml のパス。",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="評価結果の出力先ディレクトリ。",
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
    raise EvaluationError(
        f"CSV列を特定できませんでした: {role}. "
        f"候補={list(candidates)}, 実際の列={fieldnames}"
    )


def _resolve_image_path(*, images_dir: Path, image_value: str) -> Path:
    path_text = image_value.strip()
    if not path_text:
        raise EvaluationError("画像パス列が空です。")

    candidate = Path(path_text)
    if candidate.is_absolute():
        return candidate

    normalized = path_text.replace("\\", "/")
    return (images_dir / normalized).resolve()


def _load_label_rows(*, csv_path: Path, images_dir: Path) -> list[LabelRow]:
    if not csv_path.is_file():
        raise EvaluationError(f"CSV ファイルが見つかりません: {csv_path}")

    rows: list[LabelRow] = []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        if reader.fieldnames is None:
            raise EvaluationError(f"CSVヘッダーがありません: {csv_path}")

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
            true_weapon = _normalize_true_weapon_label(
                str(row.get(label_column, ""))
            )
            if not image_value or not true_weapon:
                continue
            rows.append(
                LabelRow(
                    row_number=row_number,
                    image_value=image_value,
                    image_path=_resolve_image_path(
                        images_dir=images_dir,
                        image_value=image_value,
                    ),
                    true_weapon=true_weapon,
                )
            )

    if not rows:
        raise EvaluationError(
            "評価対象行がありません。画像パス列・正解ラベル列を確認してください。"
        )
    return rows


def _build_query_padded_gray(slot_image: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(slot_image, cv2.COLOR_BGR2GRAY)
    padding = constants.QUERY_MATCH_MAX_SHIFT_PX
    return cv2.copyMakeBorder(
        gray,
        padding,
        padding,
        padding,
        padding,
        borderType=cv2.BORDER_REPLICATE,
    )


def _safe_div(num: float, den: float) -> float:
    if den == 0:
        return 0.0
    return num / den


def _top1_accuracy(rows: list[PredictionRow]) -> float:
    if not rows:
        return 0.0
    correct = sum(
        1
        for row in rows
        if row.predicted_weapon is not None
        and row.predicted_weapon == row.true_weapon
    )
    return correct / len(rows)


def _macro_f1(rows: list[PredictionRow]) -> float:
    labels = sorted(
        {row.true_weapon for row in rows if row.predicted_weapon is not None}
        | {
            row.predicted_weapon
            for row in rows
            if row.predicted_weapon is not None
        }
    )
    if not labels:
        return 0.0

    f1_values: list[float] = []
    for label in labels:
        tp = sum(
            1
            for row in rows
            if row.predicted_weapon is not None
            and row.true_weapon == label
            and row.predicted_weapon == label
        )
        fp = sum(
            1
            for row in rows
            if row.predicted_weapon is not None
            and row.true_weapon != label
            and row.predicted_weapon == label
        )
        fn = sum(
            1
            for row in rows
            if row.predicted_weapon is not None
            and row.true_weapon == label
            and row.predicted_weapon != label
        )
        precision = _safe_div(float(tp), float(tp + fp))
        recall = _safe_div(float(tp), float(tp + fn))
        f1 = _safe_div(2.0 * precision * recall, precision + recall)
        f1_values.append(f1)
    return sum(f1_values) / len(f1_values)


def _weapon_accuracy_rows(
    rows: list[PredictionRow],
) -> list[dict[str, str | int | float]]:
    true_labels = sorted({row.true_weapon for row in rows})
    records: list[dict[str, str | int | float]] = []
    for true_weapon in true_labels:
        target = [row for row in rows if row.true_weapon == true_weapon]
        correct = sum(
            1
            for row in target
            if row.predicted_weapon is not None
            and row.predicted_weapon == true_weapon
        )
        records.append(
            {
                "weapon": true_weapon,
                "sample_count": len(target),
                "correct_count": correct,
                "accuracy": _safe_div(float(correct), float(len(target))),
            }
        )
    return records


def _confusion_labels(rows: list[PredictionRow]) -> list[str]:
    return sorted(
        {row.true_weapon for row in rows}
        | {
            row.predicted_weapon
            for row in rows
            if row.predicted_weapon is not None
        }
    )


def _confusion_matrix(
    rows: list[PredictionRow], labels: list[str]
) -> dict[str, dict[str, int]]:
    matrix = {
        true_label: {pred_label: 0 for pred_label in labels}
        for true_label in labels
    }
    for row in rows:
        if row.predicted_weapon is None:
            continue
        matrix[row.true_weapon][row.predicted_weapon] += 1
    return matrix


def _write_predictions_csv(
    *, output_path: Path, rows: list[PredictionRow]
) -> None:
    fieldnames = [
        "row_number",
        "image",
        "image_path",
        "true_weapon",
        "predicted_weapon",
        "is_correct",
        "is_unmatched",
        "best_score",
        "threshold",
        "candidate_1_weapon",
        "candidate_1_score",
        "candidate_1_threshold",
        "candidate_2_weapon",
        "candidate_2_score",
        "candidate_2_threshold",
        "candidate_3_weapon",
        "candidate_3_score",
        "candidate_3_threshold",
        "error",
    ]
    with output_path.open("w", encoding="utf-8-sig", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            record: dict[str, str | int | float | bool | None] = {
                "row_number": row.row_number,
                "image": row.image_value,
                "image_path": str(row.image_path),
                "true_weapon": row.true_weapon,
                "predicted_weapon": row.predicted_weapon or "",
                "is_correct": (
                    row.predicted_weapon == row.true_weapon
                    if row.predicted_weapon is not None
                    else ""
                ),
                "is_unmatched": (
                    row.is_unmatched if row.is_unmatched is not None else ""
                ),
                "best_score": (
                    row.best_score if row.best_score is not None else ""
                ),
                "threshold": (
                    row.threshold if row.threshold is not None else ""
                ),
                "error": row.error or "",
            }
            for idx in range(3):
                col_prefix = f"candidate_{idx + 1}"
                if idx < len(row.top_candidates):
                    candidate = row.top_candidates[idx]
                    record[f"{col_prefix}_weapon"] = candidate.weapon
                    record[f"{col_prefix}_score"] = candidate.score
                    record[f"{col_prefix}_threshold"] = candidate.threshold
                else:
                    record[f"{col_prefix}_weapon"] = ""
                    record[f"{col_prefix}_score"] = ""
                    record[f"{col_prefix}_threshold"] = ""
            writer.writerow(record)


def _write_weapon_accuracy_csv(
    *,
    output_path: Path,
    rows: list[dict[str, str | int | float]],
) -> None:
    fieldnames = ["weapon", "sample_count", "correct_count", "accuracy"]
    with output_path.open("w", encoding="utf-8-sig", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_confusion_matrix_csv(
    *,
    output_path: Path,
    labels: list[str],
    matrix: dict[str, dict[str, int]],
) -> None:
    with output_path.open("w", encoding="utf-8-sig", newline="") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(["true\\pred", *labels])
        for true_label in labels:
            writer.writerow(
                [true_label, *[matrix[true_label][pred] for pred in labels]]
            )


async def _predict_single_slot(
    *,
    recognizer: WeaponRecognitionAdapter,
    image_path: Path,
) -> tuple[
    str,
    bool,
    float | None,
    float | None,
    tuple[WeaponCandidateScore, ...],
]:
    image = imread_unicode(image_path, flags=cv2.IMREAD_COLOR)
    if image is None:
        raise EvaluationError(f"画像読み込みに失敗しました: {image_path}")

    query_padded_gray = _build_query_padded_gray(image)
    slot_signal_metrics = recognizer._compute_slot_signal_metrics(
        slot_image=image
    )
    cancel_generation = recognizer._capture_cancel_generation()
    # 現行ロジック準拠のため、1スロット判別は内部関数を利用する。
    slot_result, _debug_candidates = await recognizer._predict_slot(
        slot=constants.ALLY_SLOTS[0],
        query_padded_gray=query_padded_gray,
        cancel_generation=cancel_generation,
        slot_signal_metrics=slot_signal_metrics,
    )
    best = (
        slot_result.top_candidates[0] if slot_result.top_candidates else None
    )
    return (
        slot_result.predicted_weapon,
        slot_result.is_unmatched,
        best.score if best is not None else None,
        best.threshold if best is not None else None,
        slot_result.top_candidates,
    )


async def _evaluate_rows(
    *,
    recognizer: WeaponRecognitionAdapter,
    label_rows: list[LabelRow],
) -> list[PredictionRow]:
    results: list[PredictionRow] = []
    for row in label_rows:
        try:
            (
                predicted_weapon,
                is_unmatched,
                best_score,
                threshold,
                top_candidates,
            ) = await _predict_single_slot(
                recognizer=recognizer,
                image_path=row.image_path,
            )
            results.append(
                PredictionRow(
                    row_number=row.row_number,
                    image_value=row.image_value,
                    image_path=row.image_path,
                    true_weapon=row.true_weapon,
                    predicted_weapon=predicted_weapon,
                    is_unmatched=is_unmatched,
                    best_score=best_score,
                    threshold=threshold,
                    top_candidates=top_candidates,
                    error=None,
                )
            )
        except Exception as exc:  # pragma: no cover - 実行時エラー集約
            results.append(
                PredictionRow(
                    row_number=row.row_number,
                    image_value=row.image_value,
                    image_path=row.image_path,
                    true_weapon=row.true_weapon,
                    predicted_weapon=None,
                    is_unmatched=None,
                    best_score=None,
                    threshold=None,
                    top_candidates=(),
                    error=str(exc),
                )
            )
    return results


async def run_evaluation(args: argparse.Namespace) -> int:
    images_dir = _resolve_existing_path(args.images_dir)
    csv_path = _resolve_existing_path(args.csv)
    config_path = _resolve_existing_path(args.config)
    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = (Path.cwd() / output_dir).resolve()

    if not images_dir.is_dir():
        raise EvaluationError(
            f"--images-dir のディレクトリが見つかりません: {images_dir}"
        )
    if not csv_path.is_file():
        raise EvaluationError(f"--csv が見つかりません: {csv_path}")
    if not config_path.is_file():
        raise EvaluationError(f"--config が見つかりません: {config_path}")

    output_dir.mkdir(parents=True, exist_ok=True)

    settings = ImageMatchingSettings.load_from_yaml(config_path)
    recognizer = WeaponRecognitionAdapter(
        settings=settings,
        logger=_NullLogger(),
    )

    label_rows = _load_label_rows(csv_path=csv_path, images_dir=images_dir)
    prediction_rows = await _evaluate_rows(
        recognizer=recognizer,
        label_rows=label_rows,
    )
    valid_rows = [
        row for row in prediction_rows if row.predicted_weapon is not None
    ]

    top1_accuracy = _top1_accuracy(valid_rows)
    macro_f1 = _macro_f1(valid_rows)
    weapon_accuracy_rows = _weapon_accuracy_rows(valid_rows)
    matrix_labels = _confusion_labels(valid_rows)
    matrix = _confusion_matrix(valid_rows, matrix_labels)

    predictions_path = output_dir / "predictions.csv"
    weapon_accuracy_path = output_dir / "weapon_accuracy.csv"
    confusion_path = output_dir / "confusion_matrix.csv"
    summary_path = output_dir / "summary.json"

    _write_predictions_csv(output_path=predictions_path, rows=prediction_rows)
    _write_weapon_accuracy_csv(
        output_path=weapon_accuracy_path,
        rows=weapon_accuracy_rows,
    )
    _write_confusion_matrix_csv(
        output_path=confusion_path,
        labels=matrix_labels,
        matrix=matrix,
    )

    correct = sum(
        1
        for row in valid_rows
        if row.predicted_weapon is not None
        and row.predicted_weapon == row.true_weapon
    )
    summary = {
        "total_rows": len(prediction_rows),
        "evaluated_rows": len(valid_rows),
        "error_rows": len(prediction_rows) - len(valid_rows),
        "correct_rows": correct,
        "top1_accuracy": top1_accuracy,
        "macro_f1": macro_f1,
        "class_count": len(matrix_labels),
        "unknown_true_total": sum(
            1
            for row in valid_rows
            if row.true_weapon == constants.UNKNOWN_WEAPON_LABEL
        ),
        "unknown_true_correct": sum(
            1
            for row in valid_rows
            if row.true_weapon == constants.UNKNOWN_WEAPON_LABEL
            and row.predicted_weapon == constants.UNKNOWN_WEAPON_LABEL
        ),
        "unknown_pred_total": sum(
            1
            for row in valid_rows
            if row.predicted_weapon == constants.UNKNOWN_WEAPON_LABEL
        ),
        "unknown_prediction_count": sum(
            1
            for row in valid_rows
            if row.predicted_weapon == constants.UNKNOWN_WEAPON_LABEL
        ),
        "output_files": {
            "predictions_csv": str(predictions_path),
            "weapon_accuracy_csv": str(weapon_accuracy_path),
            "confusion_matrix_csv": str(confusion_path),
            "summary_json": str(summary_path),
        },
    }
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("評価完了")
    print(f"total_rows={summary['total_rows']}")
    print(f"evaluated_rows={summary['evaluated_rows']}")
    print(f"error_rows={summary['error_rows']}")
    print(f"top1_accuracy={summary['top1_accuracy']:.6f}")
    print(f"macro_f1={summary['macro_f1']:.6f}")
    print(f"output_dir={output_dir}")
    return 0


def main() -> int:
    args = parse_args()
    return asyncio.run(run_evaluation(args))


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except EvaluationError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        raise SystemExit(1)
