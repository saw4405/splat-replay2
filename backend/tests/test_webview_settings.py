from __future__ import annotations

from pathlib import Path

from splat_replay.infrastructure.adapters.storage.settings_repository import (
    TomlSettingsRepository,
)
from splat_replay.infrastructure.config import load_settings_from_toml


def test_load_settings_defaults_webview_render_mode_to_gpu(
    tmp_path: Path,
) -> None:
    settings_path = tmp_path / "settings.toml"

    settings = load_settings_from_toml(settings_path, create_if_missing=False)

    assert settings.webview.render_mode == "gpu"


def test_invalid_webview_render_mode_falls_back_to_gpu(
    tmp_path: Path,
) -> None:
    settings_path = tmp_path / "settings.toml"
    settings_path.write_text(
        '[webview]\nrender_mode = "broken"\n', encoding="utf-8"
    )

    settings = load_settings_from_toml(settings_path, create_if_missing=False)

    assert settings.webview.render_mode == "gpu"


def test_fetch_sections_exposes_labeled_webview_render_mode(
    tmp_path: Path,
) -> None:
    repository = TomlSettingsRepository(
        settings_path=tmp_path / "settings.toml"
    )

    sections = repository.fetch_sections()
    webview_section = next(
        section for section in sections if section["id"] == "webview"
    )
    render_mode = next(
        field
        for field in webview_section["fields"]
        if field["id"] == "render_mode"
    )

    assert render_mode["type"] == "select"
    assert render_mode["choices"] == ["cpu", "gpu"]
    assert render_mode["choice_labels"] == {
        "cpu": "CPU",
        "gpu": "GPU",
    }
    assert render_mode["value"] == "gpu"
    assert (
        "プレビュー更新頻度の変更は保存後すぐに反映されます"
        in render_mode["description"]
    )
    assert (
        "描画モードの切り替えは再起動後に反映されます"
        in render_mode["description"]
    )


def test_update_sections_persists_webview_render_mode(
    tmp_path: Path,
) -> None:
    settings_path = tmp_path / "settings.toml"
    repository = TomlSettingsRepository(settings_path=settings_path)

    repository.update_sections(
        [{"id": "webview", "values": {"render_mode": "gpu"}}]
    )

    settings = load_settings_from_toml(settings_path, create_if_missing=False)

    assert settings.webview.render_mode == "gpu"
