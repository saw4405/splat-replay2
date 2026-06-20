from __future__ import annotations


from splat_replay.domain.config import ImageMatchingSettings

MATCHING_CONFIG_PATH = (
    __import__("pathlib").Path(__file__).resolve().parents[3]
    / "config"
    / "image_matching.yaml"
)


def test_weapon_labeling_configuration_loads_successfully() -> None:
    settings = ImageMatchingSettings.load_from_yaml(MATCHING_CONFIG_PATH)
    assert settings is not None
    assert len(settings.matchers) > 0
