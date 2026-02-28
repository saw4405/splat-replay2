#!/usr/bin/env python3
"""ブキ判別評価(before/after)の差分レポート生成CLI。"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass
from pathlib import Path


class CompareError(RuntimeError):
    """比較処理で期待外の入力を検出した場合の例外。"""


@dataclass(frozen=True)
class PredictionRecord:
    """predictions.csv の1行。"""

    row_number: str
    image: str
    image_path: str
    true_weapon: str
    predicted_weapon: str
    error: str

    @property
    def is_evaluated(self) -> bool:
        return bool(self.predicted_weapon)

    @property
    def is_correct(self) -> bool:
        return self.is_evaluated and self.true_weapon == self.predicted_weapon


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="before/after のブキ判別評価差分を集計する。"
    )
    parser.add_argument(
        "--before-dir",
        required=True,
        help="before 側の評価出力ディレクトリ。",
    )
    parser.add_argument(
        "--after-dir",
        required=True,
        help="after 側の評価出力ディレクトリ。",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="差分レポート出力先ディレクトリ。",
    )
    parser.add_argument(
        "--join-key",
        default="filename",
        choices=("filename", "row_number", "image", "image_path"),
        help="before/after の突合キー。",
    )
    return parser.parse_args()


def _resolve_key_value(record: PredictionRecord, join_key: str) -> str:
    if join_key == "filename":
        return record.image
    if join_key == "row_number":
        return record.row_number
    if join_key == "image":
        return record.image
    if join_key == "image_path":
        return record.image_path
    raise CompareError(f"未対応のjoin-keyです: {join_key}")


def _load_predictions(path: Path) -> list[PredictionRecord]:
    if not path.is_file():
        raise CompareError(f"predictions.csv が見つかりません: {path}")

    with path.open("r", encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        if reader.fieldnames is None:
            raise CompareError(f"CSVヘッダーがありません: {path}")

        required = {
            "row_number",
            "image",
            "image_path",
            "true_weapon",
            "predicted_weapon",
            "error",
        }
        missing = sorted(required - set(reader.fieldnames))
        if missing:
            raise CompareError(
                f"必須列が不足しています: {missing}, file={path}"
            )

        rows: list[PredictionRecord] = []
        for row in reader:
            rows.append(
                PredictionRecord(
                    row_number=str(row.get("row_number", "")),
                    image=str(row.get("image", "")),
                    image_path=str(row.get("image_path", "")),
                    true_weapon=str(row.get("true_weapon", "")),
                    predicted_weapon=str(
                        row.get("predicted_weapon", "")
                    ).strip(),
                    error=str(row.get("error", "")).strip(),
                )
            )
    return rows


def _load_summary(path: Path) -> dict[str, object]:
    if not path.is_file():
        raise CompareError(f"summary.json が見つかりません: {path}")
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CompareError(f"JSONの読み込みに失敗しました: {path}") from exc
    if not isinstance(loaded, dict):
        raise CompareError(f"summary.json の形式が不正です: {path}")
    return loaded


def _to_float(summary: dict[str, object], key: str) -> float:
    value = summary.get(key)
    if isinstance(value, int | float):
        return float(value)
    raise CompareError(f"summary.json に数値項目がありません: {key}")


def _to_int(summary: dict[str, object], key: str) -> int:
    value = summary.get(key)
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    raise CompareError(f"summary.json に整数項目がありません: {key}")


def _safe_div(num: int, den: int) -> float:
    if den == 0:
        return 0.0
    return num / den


def _build_record_map(
    *, rows: list[PredictionRecord], join_key: str
) -> dict[str, PredictionRecord]:
    mapped: dict[str, PredictionRecord] = {}
    for row in rows:
        key = _resolve_key_value(row, join_key)
        if not key:
            raise CompareError(
                "join-key が空の行を検出しました。"
                f" row_number={row.row_number}, join_key={join_key}"
            )
        if key in mapped:
            raise CompareError(
                f"join-key が重複しています: {key}, join_key={join_key}"
            )
        mapped[key] = row
    return mapped


def _build_weapon_accuracy(
    rows: list[PredictionRecord],
) -> dict[str, tuple[int, int, float]]:
    sample_count: dict[str, int] = {}
    correct_count: dict[str, int] = {}
    for row in rows:
        weapon = row.true_weapon
        sample_count[weapon] = sample_count.get(weapon, 0) + 1
        if row.is_correct:
            correct_count[weapon] = correct_count.get(weapon, 0) + 1

    result: dict[str, tuple[int, int, float]] = {}
    for weapon, count in sample_count.items():
        correct = correct_count.get(weapon, 0)
        result[weapon] = (
            count,
            correct,
            _safe_div(correct, count),
        )
    return result


def _build_confusion(
    rows: list[PredictionRecord],
) -> dict[tuple[str, str], int]:
    matrix: dict[tuple[str, str], int] = {}
    for row in rows:
        if not row.is_evaluated:
            continue
        key = (row.true_weapon, row.predicted_weapon)
        matrix[key] = matrix.get(key, 0) + 1
    return matrix


def _write_weapon_accuracy_diff(
    *,
    output_path: Path,
    before_rows: list[PredictionRecord],
    after_rows: list[PredictionRecord],
) -> None:
    before_map = _build_weapon_accuracy(before_rows)
    after_map = _build_weapon_accuracy(after_rows)
    weapons = sorted(set(before_map) | set(after_map))

    fieldnames = [
        "weapon",
        "before_sample_count",
        "before_correct_count",
        "before_accuracy",
        "after_sample_count",
        "after_correct_count",
        "after_accuracy",
        "accuracy_delta",
    ]
    with output_path.open("w", encoding="utf-8-sig", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        for weapon in weapons:
            before_sample, before_correct, before_acc = before_map.get(
                weapon, (0, 0, 0.0)
            )
            after_sample, after_correct, after_acc = after_map.get(
                weapon, (0, 0, 0.0)
            )
            writer.writerow(
                {
                    "weapon": weapon,
                    "before_sample_count": before_sample,
                    "before_correct_count": before_correct,
                    "before_accuracy": before_acc,
                    "after_sample_count": after_sample,
                    "after_correct_count": after_correct,
                    "after_accuracy": after_acc,
                    "accuracy_delta": after_acc - before_acc,
                }
            )


def _write_confusion_matrix_diff(
    *,
    output_path: Path,
    before_rows: list[PredictionRecord],
    after_rows: list[PredictionRecord],
) -> None:
    before_conf = _build_confusion(before_rows)
    after_conf = _build_confusion(after_rows)
    labels = sorted(
        {true_label for true_label, _ in before_conf.keys()}
        | {pred_label for _, pred_label in before_conf.keys()}
        | {true_label for true_label, _ in after_conf.keys()}
        | {pred_label for _, pred_label in after_conf.keys()}
    )

    with output_path.open("w", encoding="utf-8-sig", newline="") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(["true\\pred", *labels])
        for true_label in labels:
            row_values = [true_label]
            for pred_label in labels:
                before_value = before_conf.get((true_label, pred_label), 0)
                after_value = after_conf.get((true_label, pred_label), 0)
                row_values.append(after_value - before_value)
            writer.writerow(row_values)


def _write_case_csv(
    *,
    output_path: Path,
    rows: list[tuple[str, PredictionRecord, PredictionRecord]],
    join_key: str,
) -> None:
    fieldnames = [
        join_key,
        "row_number",
        "image",
        "image_path",
        "true_weapon",
        "before_predicted_weapon",
        "after_predicted_weapon",
        "before_is_correct",
        "after_is_correct",
        "before_error",
        "after_error",
    ]
    with output_path.open("w", encoding="utf-8-sig", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        for key, before_row, after_row in rows:
            writer.writerow(
                {
                    join_key: key,
                    "row_number": after_row.row_number,
                    "image": after_row.image,
                    "image_path": after_row.image_path,
                    "true_weapon": after_row.true_weapon,
                    "before_predicted_weapon": before_row.predicted_weapon,
                    "after_predicted_weapon": after_row.predicted_weapon,
                    "before_is_correct": before_row.is_correct,
                    "after_is_correct": after_row.is_correct,
                    "before_error": before_row.error,
                    "after_error": after_row.error,
                }
            )


def run_compare(args: argparse.Namespace) -> int:
    before_dir = Path(args.before_dir)
    after_dir = Path(args.after_dir)
    output_dir = Path(args.output_dir)
    join_key: str = args.join_key

    before_predictions = _load_predictions(before_dir / "predictions.csv")
    after_predictions = _load_predictions(after_dir / "predictions.csv")
    before_summary = _load_summary(before_dir / "summary.json")
    after_summary = _load_summary(after_dir / "summary.json")

    before_map = _build_record_map(rows=before_predictions, join_key=join_key)
    after_map = _build_record_map(rows=after_predictions, join_key=join_key)
    before_keys = set(before_map)
    after_keys = set(after_map)
    if before_keys != after_keys:
        missing_after = sorted(before_keys - after_keys)[:10]
        missing_before = sorted(after_keys - before_keys)[:10]
        raise CompareError(
            "before/after の突合キー集合が一致しません。"
            f" missing_in_after={missing_after}, "
            f"missing_in_before={missing_before}"
        )

    improved_cases: list[tuple[str, PredictionRecord, PredictionRecord]] = []
    regressed_cases: list[tuple[str, PredictionRecord, PredictionRecord]] = []
    for key in sorted(before_keys):
        before_row = before_map[key]
        after_row = after_map[key]
        if (not before_row.is_correct) and after_row.is_correct:
            improved_cases.append((key, before_row, after_row))
        elif before_row.is_correct and (not after_row.is_correct):
            regressed_cases.append((key, before_row, after_row))

    output_dir.mkdir(parents=True, exist_ok=True)
    comparison_summary_path = output_dir / "comparison_summary.json"
    weapon_accuracy_diff_path = output_dir / "weapon_accuracy_diff.csv"
    confusion_matrix_diff_path = output_dir / "confusion_matrix_diff.csv"
    improved_cases_path = output_dir / "improved_cases.csv"
    regressed_cases_path = output_dir / "regressed_cases.csv"

    _write_weapon_accuracy_diff(
        output_path=weapon_accuracy_diff_path,
        before_rows=before_predictions,
        after_rows=after_predictions,
    )
    _write_confusion_matrix_diff(
        output_path=confusion_matrix_diff_path,
        before_rows=before_predictions,
        after_rows=after_predictions,
    )
    _write_case_csv(
        output_path=improved_cases_path,
        rows=improved_cases,
        join_key=join_key,
    )
    _write_case_csv(
        output_path=regressed_cases_path,
        rows=regressed_cases,
        join_key=join_key,
    )

    summary = {
        "join_key": join_key,
        "sample_count": len(before_predictions),
        "top1_before": _to_float(before_summary, "top1_accuracy"),
        "top1_after": _to_float(after_summary, "top1_accuracy"),
        "top1_delta": _to_float(after_summary, "top1_accuracy")
        - _to_float(before_summary, "top1_accuracy"),
        "macro_f1_before": _to_float(before_summary, "macro_f1"),
        "macro_f1_after": _to_float(after_summary, "macro_f1"),
        "macro_f1_delta": _to_float(after_summary, "macro_f1")
        - _to_float(before_summary, "macro_f1"),
        "unknown_true_total_before": _to_int(
            before_summary, "unknown_true_total"
        ),
        "unknown_true_total_after": _to_int(
            after_summary, "unknown_true_total"
        ),
        "unknown_true_correct_before": _to_int(
            before_summary, "unknown_true_correct"
        ),
        "unknown_true_correct_after": _to_int(
            after_summary, "unknown_true_correct"
        ),
        "unknown_pred_total_before": _to_int(
            before_summary, "unknown_pred_total"
        ),
        "unknown_pred_total_after": _to_int(
            after_summary, "unknown_pred_total"
        ),
        "improved_case_count": len(improved_cases),
        "regressed_case_count": len(regressed_cases),
        "output_files": {
            "weapon_accuracy_diff_csv": str(weapon_accuracy_diff_path),
            "confusion_matrix_diff_csv": str(confusion_matrix_diff_path),
            "improved_cases_csv": str(improved_cases_path),
            "regressed_cases_csv": str(regressed_cases_path),
            "comparison_summary_json": str(comparison_summary_path),
        },
    }
    comparison_summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("比較完了")
    print(f"sample_count={summary['sample_count']}")
    print(f"top1_before={summary['top1_before']:.6f}")
    print(f"top1_after={summary['top1_after']:.6f}")
    print(f"top1_delta={summary['top1_delta']:.6f}")
    print(f"macro_f1_before={summary['macro_f1_before']:.6f}")
    print(f"macro_f1_after={summary['macro_f1_after']:.6f}")
    print(f"macro_f1_delta={summary['macro_f1_delta']:.6f}")
    print(f"improved_case_count={summary['improved_case_count']}")
    print(f"regressed_case_count={summary['regressed_case_count']}")
    print(f"output_dir={output_dir}")
    return 0


def main() -> int:
    args = parse_args()
    return run_compare(args)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except CompareError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        raise SystemExit(1)
