"""ブキ判別（recognize_weapons）のパフォーマンス測定テスト。

このテストは性能測定を行い、処理時間の統計情報を出力します。
デフォルトではスキップされます。

実行方法:
    pytest -m perf tests/test_weapon_recognition_performance.py -v -s
"""

from __future__ import annotations

import statistics
import time
from pathlib import Path
from typing import Callable

import cv2
import numpy as np
import pytest
from splat_replay.domain.config import ImageMatchingSettings
from splat_replay.infrastructure.adapters.weapon_detection.recognizer import (
    WeaponRecognitionAdapter,
)

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "weapon_detection"
VISIBLE_FIXTURE_DIR = FIXTURE_DIR / "weapon_icons_visible"
MATCHING_CONFIG_PATH = (
    Path(__file__).resolve().parents[1] / "config" / "image_matching.yaml"
)


class _PerfLogger:
    """パフォーマンステスト用のダミーロガー。"""

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


def _load_image(path: Path) -> np.ndarray:
    """画像ファイルを読み込む。"""
    image = cv2.imread(str(path))
    if image is None:
        raise RuntimeError(f"failed to load fixture: {path}")
    return image


def _summary(times_ms: list[float]) -> dict[str, float]:
    """処理時間の統計情報を計算する。"""
    return {
        "mean_ms": statistics.fmean(times_ms),
        "median_ms": statistics.median(times_ms),
        "min_ms": min(times_ms),
        "max_ms": max(times_ms),
        "stdev_ms": statistics.stdev(times_ms) if len(times_ms) > 1 else 0.0,
    }


@pytest.mark.perf
@pytest.mark.asyncio
async def test_weapon_recognition_performance(
    perf_recorder: Callable[[dict[str, object]], None],
) -> None:
    """ブキ判別の処理時間を測定する。

    複数のサンプル画像に対してブキ判別を実行し、処理時間の統計情報を出力します。
    """
    settings = ImageMatchingSettings.load_from_yaml(MATCHING_CONFIG_PATH)
    recognizer = WeaponRecognitionAdapter(
        settings=settings,
        logger=_PerfLogger(),
    )

    # サンプル画像を読み込む
    visible_paths = sorted(
        VISIBLE_FIXTURE_DIR.glob("weapon_icons_visible_*.png")
    )
    if not visible_paths:
        pytest.skip("テスト用の画像ファイルが見つかりません")

    frames = [_load_image(path) for path in visible_paths]

    # ウォームアップ（初回ロードやキャッシュの影響を除外）
    await recognizer.recognize_weapons(frames[0], save_unmatched_report=False)

    # パフォーマンス測定（レポート出力なし）
    times_ms_no_report: list[float] = []
    for frame in frames:
        started = time.perf_counter()
        _ = await recognizer.recognize_weapons(
            frame, save_unmatched_report=False
        )
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        times_ms_no_report.append(elapsed_ms)

    # パフォーマンス測定（レポート出力あり）
    times_ms_with_report: list[float] = []
    for frame in frames:
        started = time.perf_counter()
        _ = await recognizer.recognize_weapons(
            frame, save_unmatched_report=True
        )
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        times_ms_with_report.append(elapsed_ms)

    # 統計情報を計算
    summary_no_report = _summary(times_ms_no_report)
    summary_with_report = _summary(times_ms_with_report)

    # パフォーマンス記録を保存
    perf_recorder(
        {
            "name": "recognize_weapons_no_report",
            "sample_count": len(times_ms_no_report),
            **summary_no_report,
            "runs_ms": times_ms_no_report,
        }
    )
    perf_recorder(
        {
            "name": "recognize_weapons_with_report",
            "sample_count": len(times_ms_with_report),
            **summary_with_report,
            "runs_ms": times_ms_with_report,
        }
    )

    # コンソールに結果を出力
    print("\n【ブキ判別パフォーマンス測定結果】")
    print(f"サンプル数: {len(frames)}")
    print("\n■ レポート出力なし (save_unmatched_report=False):")
    print(f"  平均: {summary_no_report['mean_ms']:.3f}ms")
    print(f"  中央値: {summary_no_report['median_ms']:.3f}ms")
    print(f"  最小: {summary_no_report['min_ms']:.3f}ms")
    print(f"  最大: {summary_no_report['max_ms']:.3f}ms")
    print(f"  標準偏差: {summary_no_report['stdev_ms']:.3f}ms")
    print("\n■ レポート出力あり (save_unmatched_report=True):")
    print(f"  平均: {summary_with_report['mean_ms']:.3f}ms")
    print(f"  中央値: {summary_with_report['median_ms']:.3f}ms")
    print(f"  最小: {summary_with_report['min_ms']:.3f}ms")
    print(f"  最大: {summary_with_report['max_ms']:.3f}ms")
    print(f"  標準偏差: {summary_with_report['stdev_ms']:.3f}ms")
    print(
        f"\nレポート出力のオーバーヘッド: "
        f"{summary_with_report['mean_ms'] - summary_no_report['mean_ms']:.3f}ms"
    )

    # 基本的なアサーション（処理が完了すること）
    assert len(times_ms_no_report) == len(frames)
    assert len(times_ms_with_report) == len(frames)
    assert all(t > 0 for t in times_ms_no_report)
    assert all(t > 0 for t in times_ms_with_report)
    assert all(t > 0 for t in times_ms_with_report)
