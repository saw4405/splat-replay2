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
NON_VISIBLE_FILENAMES = (
    "no_weapon_icons_screen.png",
    "no_weapon_icons_screen_2.png",
    "no_weapon_icons_screen_3.png",
    "no_weapon_icons_screen_4.png",
)


class _PerfLogger:
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
    image = cv2.imread(str(path))
    if image is None:
        raise RuntimeError(f"failed to load fixture: {path}")
    return image


def _summary(times_ms: list[float]) -> dict[str, float]:
    return {
        "mean_ms": statistics.fmean(times_ms),
        "min_ms": min(times_ms),
        "max_ms": max(times_ms),
    }


@pytest.mark.perf
@pytest.mark.asyncio
async def test_weapon_display_detection_performance(
    perf_recorder: Callable[[dict[str, object]], None],
) -> None:
    settings = ImageMatchingSettings.load_from_yaml(MATCHING_CONFIG_PATH)
    recognizer = WeaponRecognitionAdapter(
        settings=settings,
        logger=_PerfLogger(),
    )
    visible_paths = sorted(
        VISIBLE_FIXTURE_DIR.glob("weapon_icons_visible_*.png")
    )
    non_visible_paths = [FIXTURE_DIR / name for name in NON_VISIBLE_FILENAMES]
    visible_frames = [_load_image(path) for path in visible_paths]
    non_visible_frames = [_load_image(path) for path in non_visible_paths]

    # 初回ロードやキャッシュの揺らぎを除外するためウォームアップを行う。
    await recognizer.detect_weapon_display(visible_frames[0])

    visible_times_ms: list[float] = []
    visible_true_count = 0
    for frame in visible_frames:
        started = time.perf_counter()
        is_visible = await recognizer.detect_weapon_display(frame)
        visible_times_ms.append((time.perf_counter() - started) * 1000.0)
        if is_visible:
            visible_true_count += 1

    non_visible_times_ms: list[float] = []
    non_visible_false_count = 0
    for frame in non_visible_frames:
        started = time.perf_counter()
        is_visible = await recognizer.detect_weapon_display(frame)
        non_visible_times_ms.append((time.perf_counter() - started) * 1000.0)
        if not is_visible:
            non_visible_false_count += 1

    visible_summary = _summary(visible_times_ms)
    non_visible_summary = _summary(non_visible_times_ms)
    perf_recorder(
        {
            "name": "display_detection_visible",
            "sample_count": len(visible_times_ms),
            "visible_true_count": visible_true_count,
            **visible_summary,
            "runs_ms": visible_times_ms,
        }
    )
    perf_recorder(
        {
            "name": "display_detection_non_visible",
            "sample_count": len(non_visible_times_ms),
            "non_visible_false_count": non_visible_false_count,
            **non_visible_summary,
            "runs_ms": non_visible_times_ms,
        }
    )

    print(
        "\n表示あり: "
        f"mean={visible_summary['mean_ms']:.3f}ms "
        f"min={visible_summary['min_ms']:.3f}ms "
        f"max={visible_summary['max_ms']:.3f}ms"
    )
    print(
        "表示なし: "
        f"mean={non_visible_summary['mean_ms']:.3f}ms "
        f"min={non_visible_summary['min_ms']:.3f}ms "
        f"max={non_visible_summary['max_ms']:.3f}ms"
    )

    assert visible_true_count == len(visible_frames)
    assert non_visible_false_count == len(non_visible_frames)
