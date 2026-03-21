from __future__ import annotations

import pytest

from splat_replay.domain.config import ImageMatchingSettings

MATCHING_CONFIG_PATH = (
    __import__("pathlib").Path(__file__).resolve().parents[1]
    / "config"
    / "image_matching.yaml"
)


def test_weapon_labeling_thresholds_match_tuned_values() -> None:
    settings = ImageMatchingSettings.load_from_yaml(MATCHING_CONFIG_PATH)

    thresholds_by_name: dict[str, list[float]] = {}
    for cfg in settings.matchers.values():
        if cfg.name is None:
            continue
        thresholds_by_name.setdefault(cfg.name, []).append(cfg.threshold)

    assert thresholds_by_name["24式張替傘・乙"] == pytest.approx([0.71])
    assert thresholds_by_name["ボールドマーカーネオ"] == pytest.approx([0.81])
    assert thresholds_by_name["ジェットスイーパーカスタム"] == pytest.approx(
        [0.82, 0.82]
    )
