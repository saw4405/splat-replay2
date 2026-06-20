from __future__ import annotations

from pathlib import Path

from splat_replay.infrastructure.adapters.storage.settings_repository import (
    TomlSettingsRepository,
)
from splat_replay.infrastructure.config import load_settings_from_toml


def test_settings_repository_exposes_and_persists_record_battle_history(
    tmp_path: Path,
) -> None:
    """TomlSettingsRepository が record_battle_history 設定を正しく読み書きできることを検証。"""
    settings_path = tmp_path / "settings.toml"
    repository = TomlSettingsRepository(settings_path=settings_path)

    sections = repository.fetch_sections()
    behavior = next(
        section for section in sections if section["id"] == "behavior"
    )
    field = next(
        item
        for item in behavior["fields"]
        if item["id"] == "record_battle_history"
    )
    assert field["value"] is True

    repository.update_sections(
        [
            {
                "id": "behavior",
                "values": {
                    "edit_after_power_off": True,
                    "sleep_after_upload": False,
                    "record_battle_history": False,
                },
            }
        ]
    )

    settings = load_settings_from_toml(
        settings_path,
        create_if_missing=False,
    )
    assert settings.behavior.record_battle_history is False
