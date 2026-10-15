"""REPLAY の必須設定は実 setup API と実設定アダプターで判定する。"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from structlog.stdlib import BoundLogger

from splat_replay.application.interfaces import UploadPort
from splat_replay.application.services import (
    ErrorHandler,
    SetupService,
    SystemCheckService,
)
from splat_replay.application.services.setup.system_check_service import (
    SoftwareCheckResult,
)
from splat_replay.infrastructure.adapters.upload import NoOpUploadPort
from splat_replay.infrastructure.adapters.upload import macos_keychain
from splat_replay.infrastructure.di import configure_container, resolve
from splat_replay.infrastructure.di.runtime_profile import RuntimeProfile
from splat_replay.infrastructure.config import load_settings_from_toml
from splat_replay.infrastructure.filesystem import paths
from splat_replay.interface.web.routers.setup_navigation import (
    create_setup_navigation_router,
)


def _write_settings(
    settings_file: Path,
    storage_dir: Path,
    *,
    capture_device: str = "E2E Replay Capture",
    websocket_password: str = "e2e-only-not-a-real-password",
) -> None:
    settings_file.write_text(
        "\n".join(
            (
                "[capture_device]",
                f'name = "{capture_device}"',
                "",
                "[obs]",
                'websocket_host = "127.0.0.1"',
                "websocket_port = 4455",
                f'websocket_password = "{websocket_password}"',
                "",
                "[speech_transcriber]",
                "enabled = false",
                "",
                "[storage]",
                f"base_dir = {json.dumps(str(storage_dir))}",
                "",
                "[upload]",
                'privacy_status = "private"',
                "",
            )
        ),
        encoding="utf-8",
    )


def _create_replay_setup_client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[TestClient, Path, Path]:
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True)
    storage_dir = tmp_path / "videos"
    storage_dir.mkdir()
    settings_file = config_dir / "settings.toml"
    replay_video = tmp_path / "replay.mkv"
    replay_video.write_bytes(b"test replay input")
    (config_dir / "e2e-replay-input.json").write_text(
        json.dumps({"video_path": str(replay_video)}), encoding="utf-8"
    )
    (config_dir / "client_secret.json").write_text(
        json.dumps(
            {
                "installed": {
                    "client_id": "splat-replay-e2e.invalid",
                    "client_secret": "e2e-placeholder-not-a-credential",
                    "auth_uri": "https://example.invalid/auth",
                    "token_uri": "https://example.invalid/token",
                }
            }
        ),
        encoding="utf-8",
    )
    _write_settings(settings_file, storage_dir)

    monkeypatch.setenv("SPLAT_REPLAY_E2E_ROOT", str(tmp_path))
    monkeypatch.setenv("SPLAT_REPLAY_SETTINGS_FILE", str(settings_file))
    monkeypatch.setenv("SPLAT_REPLAY_E2E_NOOP_UPLOAD", "1")
    monkeypatch.setattr(paths, "SETTINGS_FILE", settings_file)

    def reject_keychain_access() -> None:
        raise AssertionError("REPLAY setup must not access the macOS Keychain")

    monkeypatch.setattr(
        macos_keychain, "get_youtube_oauth_token", reject_keychain_access
    )
    monkeypatch.setattr(
        SystemCheckService,
        "check_ffmpeg_installation",
        lambda self: SoftwareCheckResult(is_installed=True),
    )
    monkeypatch.setattr(
        SystemCheckService,
        "check_tesseract_installation",
        lambda self: SoftwareCheckResult(is_installed=True),
    )
    monkeypatch.setattr(
        SystemCheckService,
        "check_font_installation",
        lambda self, font_name="ikamodoki1": SoftwareCheckResult(
            is_installed=True
        ),
    )

    container = configure_container(profile=RuntimeProfile.REPLAY)
    assert isinstance(resolve(container, UploadPort), NoOpUploadPort)
    app = FastAPI()
    app.include_router(
        create_setup_navigation_router(
            resolve(container, SetupService),
            resolve(container, ErrorHandler),
            resolve(container, BoundLogger),
        ),
        prefix="/api/setup",
    )
    return TestClient(app), settings_file, storage_dir


def test_replay_setup_api_uses_real_saved_config_and_rejects_missing_values(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, settings_file, storage_dir = _create_replay_setup_client(
        tmp_path, monkeypatch
    )

    valid_response = client.get("/api/setup/status?refresh=true")
    assert valid_response.status_code == 200
    assert valid_response.json()["required_setup_issues"] == []

    completed_response = client.post("/api/setup/complete")
    assert completed_response.status_code == 200
    assert completed_response.json()["is_completed"] is True

    _write_settings(settings_file, storage_dir, capture_device="")
    missing_capture_response = client.post("/api/setup/complete")
    assert missing_capture_response.status_code == 409
    assert "capture_device_unconfigured" in {
        issue["code"]
        for issue in missing_capture_response.json()["detail"][
            "required_setup_issues"
        ]
    }

    _write_settings(
        settings_file,
        storage_dir,
        websocket_password="different-e2e-password",
    )
    mismatched_password_response = client.post("/api/setup/complete")
    assert mismatched_password_response.status_code == 409
    assert "obs_websocket_password_mismatch" in {
        issue["code"]
        for issue in mismatched_password_response.json()["detail"][
            "required_setup_issues"
        ]
    }

    _write_settings(settings_file, storage_dir)
    (tmp_path / "config" / "client_secret.json").unlink()
    missing_oauth_response = client.post("/api/setup/complete")
    assert missing_oauth_response.status_code == 409
    assert "youtube_client_secret_invalid" in {
        issue["code"]
        for issue in missing_oauth_response.json()["detail"][
            "required_setup_issues"
        ]
    }


def test_replay_settings_writer_quotes_windows_storage_paths(
    tmp_path: Path,
) -> None:
    settings_file = tmp_path / "config" / "settings.toml"
    settings_file.parent.mkdir()
    windows_storage_path = Path(r"C:\e2e\replay\videos")

    _write_settings(settings_file, windows_storage_path)
    settings = load_settings_from_toml(settings_file)

    assert str(settings.storage.base_dir) == str(windows_storage_path)
