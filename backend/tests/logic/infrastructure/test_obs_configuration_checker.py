"""OBS の保存済み NDI 設定読み取りを守る。"""

from __future__ import annotations

from pathlib import Path
from typing import cast

import json
import pytest

from splat_replay.application.interfaces import (
    EnvironmentPort,
    FileSystemPort,
    LoggerPort,
)
from splat_replay.application.services.setup.system_check_service import (
    SoftwareCheckResult,
)
from splat_replay.infrastructure.adapters.system.obs_configuration_checker import (
    OBSConfigurationChecker,
)


class _Environment:
    def __init__(self, values: dict[str, str]) -> None:
        self._values = values

    def get(self, name: str, default: str | None = None) -> str | None:
        return self._values.get(name, default)

    def set(self, name: str, value: str) -> None:
        self._values[name] = value


class _Logger:
    def __init__(self) -> None:
        self.events: list[tuple[str, str, dict[str, object]]] = []

    def info(self, event: str, **kw: object) -> None:
        self.events.append(("info", event, kw))

    def warning(self, event: str, **kw: object) -> None:
        self.events.append(("warning", event, kw))


class _OBSChecker:
    def __init__(self, executable: Path) -> None:
        self._executable = executable

    def check(self) -> SoftwareCheckResult:
        return SoftwareCheckResult(
            is_installed=True, installation_path=self._executable
        )


def _checker(
    executable: Path,
    environment: dict[str, str],
    logger: _Logger | None = None,
) -> tuple[OBSConfigurationChecker, _Logger]:
    active_logger = logger or _Logger()
    return (
        OBSConfigurationChecker(
            obs_checker=_OBSChecker(executable),
            environment=cast(EnvironmentPort, _Environment(environment)),
            file_system=cast(FileSystemPort, _LocalFileSystem()),
            logger=cast(LoggerPort, active_logger),
        ),
        active_logger,
    )


class _LocalFileSystem:
    def exists(self, path: Path) -> bool:
        return path.exists()

    def is_file(self, path: Path) -> bool:
        return path.is_file()

    def is_dir(self, path: Path) -> bool:
        return path.is_dir()

    def read_bytes(self, path: Path) -> bytes:
        return path.read_bytes()


def _write_ini(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_websocket_config(root: Path, config: str) -> None:
    _write_websocket_config_at(root / "Library/Application Support", config)


def _write_websocket_config_at(base: Path, config: str) -> None:
    path = base / "obs-studio/plugin_config/obs-websocket/config.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(config, encoding="utf-8")


def _legacy_websocket_section(
    overrides: dict[str, str] | None = None,
) -> str:
    values = {
        "FirstLoad": "false",
        "ServerEnabled": "true",
        "ServerPort": "4455",
        "AlertsEnabled": "false",
        "AuthRequired": "true",
        "ServerPassword": "saved",
    }
    values.update(overrides or {})
    return "[OBSWebSocket]\n" + "".join(
        f"{key}={value}\n" for key, value in values.items()
    )


def test_macos_reads_enabled_from_default_user_config_without_logging_values(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("sys.platform", "darwin")
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    _write_ini(
        tmp_path / "Library/Application Support/obs-studio/user.ini",
        "[NDIPlugin]\nMainOutputEnabled=true\n[Private]\nvalue=do-not-log\n",
    )
    checker, logger = _checker(
        tmp_path / "OBS.app/Contents/MacOS/OBS",
        {"HOME": str(tmp_path)},
    )

    result = checker.check()

    assert result.status == "enabled"
    assert "do-not-log" not in repr(logger.events)


def test_missing_or_false_setting_is_reported_disabled(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("sys.platform", "darwin")
    _write_ini(
        tmp_path / "Library/Application Support/obs-studio/user.ini",
        "[NDIPlugin]\nMainOutputEnabled=false\n",
    )
    checker, _ = _checker(
        tmp_path / "OBS.app/Contents/MacOS/OBS",
        {"HOME": str(tmp_path)},
    )

    assert checker.check().status == "disabled"


def test_legacy_global_value_is_used_but_conflicting_values_are_unverified(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("sys.platform", "darwin")
    config = tmp_path / "Library/Application Support/obs-studio"
    _write_ini(config / "global.ini", "[NDIPlugin]\nMainOutputEnabled=true\n")
    checker, _ = _checker(
        tmp_path / "OBS.app/Contents/MacOS/OBS",
        {"HOME": str(tmp_path)},
    )
    assert checker.check().status == "enabled"

    _write_ini(config / "user.ini", "[NDIPlugin]\nMainOutputEnabled=false\n")
    assert checker.check().status == "unverified"


def test_macos_reads_configured_location_and_falls_back_when_it_is_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("sys.platform", "darwin")
    default = tmp_path / "Library/Application Support/obs-studio"
    custom_base = tmp_path / "custom-observer"
    _write_ini(
        default / "global.ini",
        f"[Locations]\nConfiguration={custom_base}\n",
    )
    _write_ini(
        custom_base / "obs-studio/user.ini",
        "[NDIPlugin]\nMainOutputEnabled=true\n",
    )
    checker, _ = _checker(
        tmp_path / "OBS.app/Contents/MacOS/OBS",
        {"HOME": str(tmp_path)},
    )
    assert checker.check().status == "enabled"

    (custom_base / "obs-studio/user.ini").unlink()
    (custom_base / "obs-studio").rmdir()
    custom_base.rmdir()
    (default / "user.ini").write_text(
        "[NDIPlugin]\nMainOutputEnabled=false\n", encoding="utf-8"
    )
    assert checker.check().status == "disabled"


def test_macos_relative_configuration_location_is_unverified(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("sys.platform", "darwin")
    default = tmp_path / "Library/Application Support/obs-studio"
    _write_ini(
        default / "global.ini",
        "[Locations]\nConfiguration=relative/config\n",
    )
    _write_ini(
        default / "user.ini",
        "[NDIPlugin]\nMainOutputEnabled=true\n",
    )
    checker, _ = _checker(
        tmp_path / "OBS.app/Contents/MacOS/OBS",
        {"HOME": str(tmp_path)},
    )

    assert checker.check().status == "unverified"


def test_existing_non_directory_configuration_location_is_unverified(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("sys.platform", "darwin")
    default = tmp_path / "Library/Application Support/obs-studio"
    config_file = tmp_path / "not-a-directory"
    config_file.write_text("", encoding="utf-8")
    _write_ini(
        default / "global.ini",
        f"[Locations]\nConfiguration={config_file}\n",
    )
    _write_ini(
        default / "user.ini",
        "[NDIPlugin]\nMainOutputEnabled=true\n",
    )
    checker, _ = _checker(
        tmp_path / "OBS.app/Contents/MacOS/OBS",
        {"HOME": str(tmp_path)},
    )

    assert checker.check().status == "unverified"


def test_windows_portable_marker_selects_the_portable_config_root(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("sys.platform", "win32")
    executable = tmp_path / "portable/bin/64bit/obs64.exe"
    obs_root = tmp_path / "portable"
    obs_root.mkdir(parents=True)
    (obs_root / "portable_mode").write_text("", encoding="utf-8")
    _write_ini(
        obs_root / "config/obs-studio/user.ini",
        "[NDIPlugin]\nMainOutputEnabled=true\n",
    )
    _write_ini(
        obs_root / "config/obs-studio/global.ini",
        f"[Locations]\nConfiguration={tmp_path / 'external-config'}\n",
    )
    _write_ini(
        tmp_path / "external-config/obs-studio/user.ini",
        "[NDIPlugin]\nMainOutputEnabled=false\n",
    )
    _write_ini(
        tmp_path / "roaming/obs-studio/user.ini",
        "[NDIPlugin]\nMainOutputEnabled=false\n",
    )
    checker, _ = _checker(
        executable,
        {"APPDATA": str(tmp_path / "roaming")},
    )

    assert checker.check().status == "enabled"


def test_unparseable_config_is_unverified_instead_of_silent_success(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("sys.platform", "darwin")
    _write_ini(
        tmp_path / "Library/Application Support/obs-studio/user.ini",
        "this is not an ini file",
    )
    checker, _ = _checker(
        tmp_path / "OBS.app/Contents/MacOS/OBS",
        {"HOME": str(tmp_path)},
    )

    assert checker.check().status == "unverified"


def test_local_websocket_matches_saved_server_settings_without_exposing_secret(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("sys.platform", "darwin")
    password = "  saved password  "
    _write_websocket_config(
        tmp_path,
        json.dumps(
            {
                "server_enabled": True,
                "server_port": 4455,
                "auth_required": True,
                "server_password": password,
            }
        ),
    )
    checker, logger = _checker(
        tmp_path / "OBS.app/Contents/MacOS/OBS",
        {"HOME": str(tmp_path)},
    )

    result = checker.check_websocket("localhost", 4455, password)

    assert result.status == "ready"
    assert password not in repr(result)
    assert password not in repr(logger.events)


@pytest.mark.parametrize(
    "override_content",
    [
        '{"server_enabled":true,"server_port":4456,"auth_required":true,"server_password":"wrong"}',
        "not-json",
        None,
    ],
)
def test_websocket_reads_global_module_config_not_location_override(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    override_content: str | None,
) -> None:
    monkeypatch.setattr("sys.platform", "darwin")
    module_base = tmp_path / "Library/Application Support"
    custom_base = tmp_path / "custom-config"
    _write_ini(
        module_base / "obs-studio/global.ini",
        f"[Locations]\nConfiguration={custom_base}\n",
    )
    config = {
        "server_enabled": True,
        "server_port": 4455,
        "auth_required": True,
        "server_password": "saved",
    }
    _write_websocket_config_at(module_base, json.dumps(config))
    if override_content is not None:
        _write_websocket_config_at(custom_base, override_content)
    checker, _ = _checker(
        tmp_path / "OBS.app/Contents/MacOS/OBS",
        {"HOME": str(tmp_path)},
    )

    assert (
        checker.check_websocket("localhost", 4455, "saved").status == "ready"
    )


def test_websocket_checks_global_module_config_with_invalid_location_override(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("sys.platform", "darwin")
    module_base = tmp_path / "Library/Application Support"
    invalid_base = tmp_path / "not-a-directory"
    invalid_base.write_text("", encoding="utf-8")
    _write_ini(
        module_base / "obs-studio/global.ini",
        f"[Locations]\nConfiguration={invalid_base}\n",
    )
    _write_websocket_config_at(
        module_base,
        json.dumps(
            {
                "server_enabled": True,
                "server_port": 4455,
                "auth_required": True,
                "server_password": "saved",
            }
        ),
    )
    checker, _ = _checker(
        tmp_path / "OBS.app/Contents/MacOS/OBS",
        {"HOME": str(tmp_path)},
    )

    assert (
        checker.check_websocket("localhost", 4455, "saved").status == "ready"
    )


def test_complete_legacy_settings_take_precedence_over_conflicting_json(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("sys.platform", "darwin")
    module_base = tmp_path / "Library/Application Support"
    global_ini = module_base / "obs-studio/global.ini"
    config_path = (
        module_base / "obs-studio/plugin_config/obs-websocket/config.json"
    )
    _write_ini(
        global_ini,
        _legacy_websocket_section(),
    )
    _write_websocket_config_at(
        module_base,
        json.dumps(
            {
                "server_enabled": False,
                "server_port": 4456,
                "auth_required": True,
                "server_password": "json-secret",
            }
        ),
    )
    checker, logger = _checker(
        tmp_path / "OBS.app/Contents/MacOS/OBS",
        {"HOME": str(tmp_path)},
    )

    result = checker.check_websocket("localhost", 4455, "saved")

    assert result.status == "ready"
    assert (
        global_ini.read_text(encoding="utf-8") == _legacy_websocket_section()
    )
    assert "json-secret" in config_path.read_text(encoding="utf-8")
    assert "saved" not in repr(logger.events)
    assert "json-secret" not in repr(logger.events)


def test_partial_legacy_settings_are_unverified_even_with_ready_json(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("sys.platform", "darwin")
    module_base = tmp_path / "Library/Application Support"
    _write_ini(
        module_base / "obs-studio/global.ini",
        "[OBSWebSocket]\nServerEnabled=true\n",
    )
    _write_websocket_config_at(
        module_base,
        json.dumps(
            {
                "server_enabled": True,
                "server_port": 4455,
                "auth_required": True,
                "server_password": "saved",
            }
        ),
    )
    checker, logger = _checker(
        tmp_path / "OBS.app/Contents/MacOS/OBS",
        {"HOME": str(tmp_path)},
    )

    result = checker.check_websocket("localhost", 4455, "saved")

    assert result.status == "unverified"
    assert "saved" not in repr(result)
    assert "saved" not in repr(logger.events)


@pytest.mark.parametrize(
    ("overrides", "port", "password", "expected"),
    [
        ({}, 4455, "saved", "ready"),
        ({"ServerEnabled": "TrUe"}, 4455, "saved", "ready"),
        ({"ServerEnabled": "false"}, 4455, "saved", "disabled"),
        ({"ServerEnabled": " true "}, 4455, "saved", "unverified"),
        ({"ServerPort": "0x1168"}, 4455, "saved", "port_mismatch"),
        (
            {"ServerPassword": "other-secret"},
            4455,
            "saved",
            "password_mismatch",
        ),
        (
            {"AuthRequired": "0", "ServerPassword": "other-secret"},
            4455,
            "saved",
            "ready",
        ),
        ({"ServerEnabled": "yes"}, 4455, "saved", "unverified"),
        ({"ServerPort": "70000"}, 4455, "saved", "unverified"),
        ({"ServerPassword": " saved "}, 4455, " saved ", "ready"),
        ({"ServerPassword": " saved "}, 4455, "saved", "password_mismatch"),
        ({"ServerPassword": r"saved\\key"}, 4455, r"saved\key", "ready"),
        ({"ServerPassword": r"saved\nnext"}, 4455, "saved\nnext", "ready"),
        ({"ServerPassword": '"quoted"'}, 4455, '"quoted"', "ready"),
    ],
)
def test_complete_legacy_file_settings_are_compared_without_json(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    overrides: dict[str, str],
    port: int,
    password: str,
    expected: str,
) -> None:
    monkeypatch.setattr("sys.platform", "darwin")
    module_base = tmp_path / "Library/Application Support"
    _write_ini(
        module_base / "obs-studio/global.ini",
        _legacy_websocket_section(overrides),
    )
    checker, logger = _checker(
        tmp_path / "OBS.app/Contents/MacOS/OBS",
        {"HOME": str(tmp_path)},
    )

    result = checker.check_websocket("localhost", port, password)

    assert result.status == expected
    assert "other-secret" not in repr(result)
    assert "saved" not in repr(logger.events)


@pytest.mark.parametrize(
    "legacy_section",
    ["[OBSWebSocket]\n", "[OBSWebSocket]\nUnknownSetting=true\n"],
)
def test_empty_or_unknown_legacy_websocket_section_does_not_block_json(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    legacy_section: str,
) -> None:
    monkeypatch.setattr("sys.platform", "darwin")
    module_base = tmp_path / "Library/Application Support"
    _write_ini(
        module_base / "obs-studio/global.ini",
        legacy_section,
    )
    _write_websocket_config_at(
        module_base,
        json.dumps(
            {
                "server_enabled": True,
                "server_port": 4455,
                "auth_required": True,
                "server_password": "saved",
            }
        ),
    )
    checker, _ = _checker(
        tmp_path / "OBS.app/Contents/MacOS/OBS",
        {"HOME": str(tmp_path)},
    )

    assert (
        checker.check_websocket("localhost", 4455, "saved").status == "ready"
    )


def test_ipv4_mapped_ipv6_loopback_is_checked_locally(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("sys.platform", "darwin")
    _write_websocket_config(
        tmp_path,
        json.dumps(
            {
                "server_enabled": True,
                "server_port": 4455,
                "auth_required": True,
                "server_password": "saved",
            }
        ),
    )
    checker, _ = _checker(
        tmp_path / "OBS.app/Contents/MacOS/OBS",
        {"HOME": str(tmp_path)},
    )

    assert (
        checker.check_websocket("[::ffff:127.0.0.1]", 4455, "saved").status
        == "ready"
    )


@pytest.mark.parametrize(
    ("config", "port", "password", "expected"),
    [
        ({"server_enabled": False}, 4455, "saved", "disabled"),
        (
            {
                "server_enabled": True,
                "server_port": 4456,
                "auth_required": True,
                "server_password": "saved",
            },
            4455,
            "saved",
            "port_mismatch",
        ),
        (
            {
                "server_enabled": True,
                "server_port": 4455,
                "auth_required": True,
                "server_password": "other-secret",
            },
            4455,
            "saved",
            "password_mismatch",
        ),
        (
            {
                "server_enabled": True,
                "server_port": 4455,
                "auth_required": False,
                "server_password": "other-secret",
            },
            4455,
            "saved",
            "ready",
        ),
    ],
)
def test_local_websocket_reports_only_required_saved_config_mismatches(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    config: dict[str, object],
    port: int,
    password: str,
    expected: str,
) -> None:
    monkeypatch.setattr("sys.platform", "darwin")
    secret = str(config.get("server_password", ""))
    _write_websocket_config(tmp_path, json.dumps(config))
    checker, logger = _checker(
        tmp_path / "OBS.app/Contents/MacOS/OBS",
        {"HOME": str(tmp_path)},
    )

    result = checker.check_websocket("127.0.0.1", port, password)

    assert result.status == expected
    assert not secret or secret not in repr(result)
    assert not secret or secret not in repr(logger.events)


def test_remote_websocket_host_is_not_resolved_or_checked_locally(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("sys.platform", "darwin")
    checker, _ = _checker(
        Path("/Applications/OBS.app/Contents/MacOS/OBS"),
        {"HOME": str(tmp_path)},
    )

    assert (
        checker.check_websocket("obs.example.invalid", 4455, "saved").status
        == "not_applicable"
    )


def test_unreadable_websocket_json_is_unverified_without_logging_content(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("sys.platform", "darwin")
    secret = "do-not-log-websocket-password"
    _write_websocket_config(tmp_path, f"not-json {secret}")
    checker, logger = _checker(
        tmp_path / "OBS.app/Contents/MacOS/OBS",
        {"HOME": str(tmp_path)},
    )

    result = checker.check_websocket("::1", 4455, secret)

    assert result.status == "unverified"
    assert secret not in repr(result)
    assert secret not in repr(logger.events)
