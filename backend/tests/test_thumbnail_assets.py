from __future__ import annotations

from pathlib import Path

from splat_replay.domain.models import Stage


def test_thumbnail_stage_assets_exist_for_all_stage_values() -> None:
    asset_dir = Path(__file__).parents[1] / "assets" / "thumbnail"

    missing_assets = [
        f"{stage.value}.png"
        for stage in Stage
        if not (asset_dir / f"{stage.value}.png").is_file()
    ]

    assert missing_assets == []
