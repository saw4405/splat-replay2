"""実行プロファイルによる DI 構成のテスト。"""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
from typing import cast

import punq
import pytest
import splat_replay.infrastructure.di as di_module
from splat_replay.application.interfaces import (
    CaptureDeviceEnumeratorPort,
    CaptureDevicePort,
    CapturePort,
    MicrophoneEnumeratorPort,
    PathsPort,
    OCRPort,
    PowerPort,
    UploadPort,
    VideoRecorderPort,
    WeaponRecognitionPort,
)
from splat_replay.application.services.checkers import (
    DistroAVChecker,
    OBSChecker,
)
from splat_replay.application.services.setup.system_check_service import (
    SystemCheckService,
)
from splat_replay.domain.ports import BattleMedalRecognizerPort
from splat_replay.infrastructure.adapters.capture.adaptive_capture import (
    AdaptiveCapture,
)
from splat_replay.infrastructure.adapters.capture.adaptive_capture_device_checker import (
    AdaptiveCaptureDeviceChecker,
)
from splat_replay.infrastructure.adapters.medal_detection.replay_recognizer import (
    ReplayBattleMedalRecognizerAdapter,
)
from splat_replay.infrastructure.adapters.system.replay_runtime import (
    ReplayCaptureDeviceEnumerator,
    ReplayMicrophoneEnumerator,
    ReplayPower,
    ReplaySoftwareChecker,
)
from splat_replay.infrastructure.adapters.system.ndi_runtime_checker import (
    NDIRuntimeChecker,
)
from splat_replay.infrastructure.adapters.upload import NoOpUploadPort
from splat_replay.infrastructure.adapters.text.replay_ocr import (
    ReplayOCRAdapter,
)
from splat_replay.infrastructure.adapters.video.adaptive_video_recorder import (
    AdaptiveVideoRecorder,
)
from splat_replay.infrastructure.adapters.weapon_detection.replay_recognizer import (
    ReplayWeaponRecognitionAdapter,
)
from splat_replay.infrastructure.di import configure_container, resolve
from splat_replay.infrastructure.di.runtime_profile import (
    RUNTIME_PROFILE_ENV,
    RuntimeProfile,
    resolve_runtime_profile,
)
from splat_replay.infrastructure.filesystem import paths


def _configure_replay_input(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings_path = tmp_path / "config" / "settings.toml"
    replay_video = tmp_path / "replay.mkv"
    replay_video.write_bytes(b"replay input")
    settings_path.parent.mkdir(parents=True)
    settings_path.write_text(
        f"[storage]\nbase_dir = {json.dumps(str(tmp_path / 'videos'))}\n",
        encoding="utf-8",
    )
    (settings_path.parent / "e2e-replay-input.json").write_text(
        json.dumps({"video_path": str(replay_video)}), encoding="utf-8"
    )
    monkeypatch.setenv("SPLAT_REPLAY_SETTINGS_FILE", str(settings_path))
    monkeypatch.setenv("SPLAT_REPLAY_E2E_ROOT", str(tmp_path))
    monkeypatch.setenv("SPLAT_REPLAY_E2E_NOOP_UPLOAD", "1")
    monkeypatch.setattr(paths, "SETTINGS_FILE", settings_path)


def test_runtime_profile_defaults_to_live(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(RUNTIME_PROFILE_ENV, raising=False)

    assert resolve_runtime_profile() is RuntimeProfile.LIVE


def test_runtime_profile_accepts_replay_value() -> None:
    assert resolve_runtime_profile(" RePlAy ") is RuntimeProfile.REPLAY


def test_runtime_profile_rejects_unknown_value() -> None:
    with pytest.raises(ValueError, match=RUNTIME_PROFILE_ENV):
        resolve_runtime_profile("preview")


def test_live_profile_resolves_adaptive_adapters() -> None:
    container = configure_container(profile=RuntimeProfile.LIVE)

    assert isinstance(resolve(container, CapturePort), AdaptiveCapture)
    assert isinstance(
        resolve(container, CaptureDevicePort), AdaptiveCaptureDeviceChecker
    )
    assert isinstance(
        resolve(container, VideoRecorderPort), AdaptiveVideoRecorder
    )
    assert isinstance(resolve(container, OBSChecker), OBSChecker)
    assert isinstance(resolve(container, NDIRuntimeChecker), NDIRuntimeChecker)


def test_container_configures_opencv_before_runtime_start(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []

    def configure_threads() -> None:
        events.append("opencv")

    def start_runtime(self: di_module.AppRuntime) -> None:
        events.append("runtime")

    monkeypatch.setattr(
        di_module, "configure_opencv_thread_limit", configure_threads
    )
    monkeypatch.setattr(di_module.AppRuntime, "start", start_runtime)

    configure_container(profile=RuntimeProfile.LIVE)

    assert events == ["opencv", "runtime"]


def test_replay_profile_registers_only_replay_device_adapters(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_replay_input(tmp_path, monkeypatch)

    container = configure_container(profile=RuntimeProfile.REPLAY)

    assert isinstance(resolve(container, CapturePort), AdaptiveCapture)
    assert isinstance(
        resolve(container, CaptureDevicePort), AdaptiveCaptureDeviceChecker
    )
    assert isinstance(
        resolve(container, VideoRecorderPort), AdaptiveVideoRecorder
    )
    assert isinstance(
        resolve(container, CaptureDeviceEnumeratorPort),
        ReplayCaptureDeviceEnumerator,
    )
    assert isinstance(
        resolve(container, MicrophoneEnumeratorPort),
        ReplayMicrophoneEnumerator,
    )
    assert isinstance(resolve(container, PowerPort), ReplayPower)
    assert isinstance(resolve(container, OCRPort), ReplayOCRAdapter)
    assert isinstance(
        resolve(container, BattleMedalRecognizerPort),
        ReplayBattleMedalRecognizerAdapter,
    )
    assert isinstance(
        resolve(container, WeaponRecognitionPort),
        ReplayWeaponRecognitionAdapter,
    )


def test_replay_profile_isolates_external_setup_checks_and_oauth_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_replay_input(tmp_path, monkeypatch)
    container = configure_container(profile=RuntimeProfile.REPLAY)

    assert isinstance(resolve(container, OBSChecker), ReplaySoftwareChecker)
    assert isinstance(
        resolve(container, DistroAVChecker), ReplaySoftwareChecker
    )
    assert isinstance(
        resolve(container, NDIRuntimeChecker), ReplaySoftwareChecker
    )
    assert isinstance(resolve(container, UploadPort), NoOpUploadPort)

    paths_port = resolve(container, PathsPort)
    assert paths_port.get_config_dir() == tmp_path / "config"

    config_dir = paths_port.get_config_dir()
    config_dir.mkdir(parents=True, exist_ok=True)
    credentials_path = config_dir / "client_secret.json"
    credentials_path.write_text(
        json.dumps(
            {
                "installed": {
                    "client_id": "replay-test.invalid",
                    "client_secret": "not-a-credential",
                    "auth_uri": "https://example.invalid/auth",
                    "token_uri": "https://example.invalid/token",
                }
            }
        ),
        encoding="utf-8",
    )

    checks = resolve(container, SystemCheckService)
    assert checks.check_obs_installation().is_installed
    assert checks.check_distroav_installation().is_installed
    assert checks.check_ndi_runtime_installation().is_installed
    assert checks.check_obs_main_output().status == "enabled"
    assert (
        checks.check_obs_websocket_configuration(
            "127.0.0.1", 4455, "e2e-only-not-a-real-password"
        ).status
        == "ready"
    )
    assert checks.check_youtube_credentials().is_installed

    credentials_path.unlink()
    assert not checks.check_youtube_credentials().is_installed


def test_replay_rejects_external_storage_without_changing_its_contents(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    e2e_root = tmp_path / "e2e-root"
    config_dir = e2e_root / "config"
    config_dir.mkdir(parents=True)
    settings_path = config_dir / "settings.toml"
    replay_video = e2e_root / "replay.mkv"
    replay_video.write_bytes(b"replay input")
    (config_dir / "e2e-replay-input.json").write_text(
        json.dumps({"video_path": str(replay_video)}), encoding="utf-8"
    )

    external_storage = tmp_path / "external-storage"
    external_storage.mkdir()
    (external_storage / "recorded.mkv").write_bytes(b"recording")
    (external_storage / "recorded.json").write_text(
        "metadata", encoding="utf-8"
    )
    before = {
        path.relative_to(external_storage): path.read_bytes()
        for path in external_storage.rglob("*")
        if path.is_file()
    }
    settings_path.write_text(
        f"[storage]\nbase_dir = {json.dumps(str(external_storage))}\n",
        encoding="utf-8",
    )

    monkeypatch.setenv("SPLAT_REPLAY_E2E_ROOT", str(e2e_root))
    monkeypatch.setenv("SPLAT_REPLAY_SETTINGS_FILE", str(settings_path))
    monkeypatch.setenv("SPLAT_REPLAY_E2E_NOOP_UPLOAD", "1")
    monkeypatch.setattr(paths, "SETTINGS_FILE", settings_path)
    runtime_start_calls: list[bool] = []
    monkeypatch.setattr(
        di_module.AppRuntime,
        "start",
        lambda self: runtime_start_calls.append(True),
    )

    with pytest.raises(RuntimeError, match="動画保存先"):
        configure_container(profile=RuntimeProfile.REPLAY)

    after = {
        path.relative_to(external_storage): path.read_bytes()
        for path in external_storage.rglob("*")
        if path.is_file()
    }
    assert after == before
    assert runtime_start_calls == []


@pytest.mark.parametrize(
    ("root_value", "settings_path_kind"),
    [
        (None, "inside"),
        ("relative-e2e-root", "inside"),
        ("absolute", "relative"),
        ("absolute", "outside"),
    ],
)
def test_replay_rejects_nonisolated_settings_paths_before_reading_toml(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    root_value: str | None,
    settings_path_kind: str,
) -> None:
    isolation_root = tmp_path / "e2e-root"
    config_dir = isolation_root / "config"
    config_dir.mkdir(parents=True)
    inside_settings = config_dir / "settings.toml"
    inside_settings.write_text("malformed = [", encoding="utf-8")
    replay_video = tmp_path / "replay.mkv"
    replay_video.write_bytes(b"replay input")
    (config_dir / "e2e-replay-input.json").write_text(
        json.dumps({"video_path": str(replay_video)}), encoding="utf-8"
    )

    if root_value is None:
        monkeypatch.delenv("SPLAT_REPLAY_E2E_ROOT", raising=False)
    elif root_value == "absolute":
        monkeypatch.setenv("SPLAT_REPLAY_E2E_ROOT", str(isolation_root))
    else:
        monkeypatch.setenv("SPLAT_REPLAY_E2E_ROOT", root_value)

    if settings_path_kind == "inside":
        settings_path = inside_settings
    elif settings_path_kind == "relative":
        settings_path = Path("relative-settings/settings.toml")
    else:
        settings_path = tmp_path / "outside" / "settings.toml"
    monkeypatch.setattr(paths, "SETTINGS_FILE", settings_path)
    monkeypatch.setenv("SPLAT_REPLAY_SETTINGS_FILE", str(settings_path))
    monkeypatch.setenv("SPLAT_REPLAY_E2E_NOOP_UPLOAD", "1")

    error = (
        "SPLAT_REPLAY_E2E_ROOT"
        if root_value in {None, "relative-e2e-root"}
        else "設定ファイル"
    )
    with pytest.raises(RuntimeError, match=error):
        configure_container(profile=RuntimeProfile.REPLAY)


def test_replay_requires_noop_upload_to_avoid_youtube_authentication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_replay_input(tmp_path, monkeypatch)
    monkeypatch.delenv("SPLAT_REPLAY_E2E_NOOP_UPLOAD")

    with pytest.raises(RuntimeError, match="SPLAT_REPLAY_E2E_NOOP_UPLOAD=1"):
        configure_container(profile=RuntimeProfile.REPLAY)


@pytest.mark.asyncio
async def test_replay_profile_rejects_power_operation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_replay_input(tmp_path, monkeypatch)
    container = configure_container(profile=RuntimeProfile.REPLAY)

    with pytest.raises(RuntimeError, match="電源操作"):
        await resolve(container, PowerPort).sleep()


def test_replay_profile_requires_input_before_adapter_registration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings_path = tmp_path / "config" / "settings.toml"
    settings_path.parent.mkdir(parents=True)
    monkeypatch.setenv("SPLAT_REPLAY_SETTINGS_FILE", str(settings_path))
    monkeypatch.setenv("SPLAT_REPLAY_E2E_ROOT", str(tmp_path))
    monkeypatch.setenv("SPLAT_REPLAY_E2E_NOOP_UPLOAD", "1")
    monkeypatch.setattr(paths, "SETTINGS_FILE", settings_path)
    opencv_configuration_calls: list[bool] = []
    monkeypatch.setattr(
        di_module,
        "configure_opencv_thread_limit",
        lambda: opencv_configuration_calls.append(True),
    )

    with pytest.raises(RuntimeError, match="replay 入力"):
        configure_container(profile=RuntimeProfile.REPLAY)

    assert opencv_configuration_calls == []


def test_replay_profile_does_not_import_live_native_adapters(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """replay の Composition Root は live 専用 native 依存へ到達しない。"""
    _configure_replay_input(tmp_path, monkeypatch)
    settings_path = tmp_path / "config" / "settings.toml"
    script = """
import importlib.abc
import sys

BLOCKED_PREFIXES = (
    "cyndilib",
    "pytesseract",
    "splat_replay.infrastructure.adapters.capture.ndi_capture",
    "splat_replay.infrastructure.adapters.obs",
    "splat_replay.infrastructure.adapters.medal_detection.recognizer",
    "splat_replay.infrastructure.adapters.text.tesseract_ocr",
    "splat_replay.infrastructure.adapters.weapon_detection.recognizer",
)


class LiveNativeDependencyBlocker(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if any(
            fullname == prefix or fullname.startswith(f"{prefix}.")
            for prefix in BLOCKED_PREFIXES
        ):
            raise ModuleNotFoundError(f"replay must not import {fullname}")
        return None


sys.meta_path.insert(0, LiveNativeDependencyBlocker())

from splat_replay.application.interfaces import (
    CaptureDevicePort,
    CapturePort,
    VideoRecorderPort,
)
from splat_replay.infrastructure.di import configure_container, resolve
from splat_replay.infrastructure.di.runtime_profile import RuntimeProfile

container = configure_container(profile=RuntimeProfile.REPLAY)
resolve(container, CaptureDevicePort)
resolve(container, CapturePort)
resolve(container, VideoRecorderPort)

assert not any(
    module == prefix or module.startswith(f"{prefix}.")
    for module in sys.modules
    for prefix in BLOCKED_PREFIXES
)
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path(__file__).resolve().parents[3],
        env={**os.environ, "SPLAT_REPLAY_SETTINGS_FILE": str(settings_path)},
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def test_cli_composition_root_resolves_runtime_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CLI も Web と同じ実行プロファイルを Composition Root へ渡す。"""
    from splat_replay.bootstrap import cli

    captured_profiles: list[RuntimeProfile] = []
    container = cast(punq.Container, object())

    def _configure_container(*, profile: RuntimeProfile) -> punq.Container:
        captured_profiles.append(profile)
        return container

    monkeypatch.setattr(
        cli, "resolve_runtime_profile", lambda: RuntimeProfile.REPLAY
    )
    monkeypatch.setattr(cli, "configure_container", _configure_container)

    resources = cli._LazyResources()

    assert resources.container() is container
    assert captured_profiles == [RuntimeProfile.REPLAY]
