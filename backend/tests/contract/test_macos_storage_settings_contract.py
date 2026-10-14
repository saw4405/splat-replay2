from __future__ import annotations

from pathlib import Path

import pytest
import tomli_w

from splat_replay.infrastructure.config import (
    load_settings_from_toml,
    save_settings_to_toml,
)
from splat_replay.infrastructure.filesystem import paths

pytestmark = pytest.mark.contract


def test_macos_relative_video_path_survives_settings_round_trip(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    data_root = tmp_path / "Application Support" / "SplatReplay"
    settings_file = tmp_path / "config" / "settings.toml"
    monkeypatch.setattr(paths, "IS_MACOS_FROZEN", True)
    monkeypatch.setattr(paths, "RUNTIME_ROOT", data_root)

    settings = load_settings_from_toml(settings_file)
    expected_video_dir = data_root / "videos"
    assert settings.storage.base_dir == expected_video_dir

    save_settings_to_toml(settings, settings_file)
    reloaded = load_settings_from_toml(settings_file, create_if_missing=False)

    assert reloaded.storage.base_dir == expected_video_dir


def test_macos_absolute_video_path_is_preserved(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    custom_video_dir = (tmp_path / "custom videos").resolve()
    settings_file = tmp_path / "settings.toml"
    settings_file.write_text(
        tomli_w.dumps({"storage": {"base_dir": str(custom_video_dir)}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(paths, "IS_MACOS_FROZEN", True)
    monkeypatch.setattr(
        paths, "RUNTIME_ROOT", tmp_path / "Application Support"
    )

    settings = load_settings_from_toml(settings_file, create_if_missing=False)

    assert settings.storage.base_dir == custom_video_dir


def test_non_macos_settings_keep_relative_video_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    settings_file = tmp_path / "settings.toml"
    settings_file.write_text(
        '[storage]\nbase_dir = "videos"\n', encoding="utf-8"
    )
    monkeypatch.setattr(paths, "IS_MACOS_FROZEN", False)

    settings = load_settings_from_toml(settings_file, create_if_missing=False)

    assert settings.storage.base_dir == Path("videos")
