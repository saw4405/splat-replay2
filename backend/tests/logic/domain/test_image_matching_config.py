from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from splat_replay.domain.config import ImageMatchingSettings


def test_repository_image_matching_config_has_valid_references() -> None:
    config_path = (
        Path(__file__).resolve().parents[3] / "config" / "image_matching.yaml"
    )

    settings = ImageMatchingSettings.load_from_yaml(config_path)

    assert "power_off" in settings.composites
    assert "power_off_template" in settings.matchers


def test_unknown_composite_matcher_reference_is_rejected() -> None:
    with pytest.raises(ValidationError, match="unknown_matcher"):
        ImageMatchingSettings.parse_obj(
            {
                "matchers": {},
                "composites": {
                    "power_off": {"rule": {"matcher": "unknown_matcher"}}
                },
            }
        )


def test_unknown_matcher_group_reference_is_rejected() -> None:
    with pytest.raises(ValidationError, match="unknown_matcher"):
        ImageMatchingSettings.parse_obj(
            {
                "matchers": {},
                "matcher_groups": {"group": ["unknown_matcher"]},
            }
        )
