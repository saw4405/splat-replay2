"""OBS の保存済み NDI / WebSocket 設定を読み取り確認する adapter。"""

from __future__ import annotations

import configparser
import ipaddress
import json
import re
import sys
from pathlib import Path
from typing import cast

from splat_replay.application.interfaces import (
    EnvironmentPort,
    FileSystemPort,
    LoggerPort,
    OBSMainOutputCheckResult,
    OBSWebSocketCheckResult,
)
from splat_replay.application.services.system.software_checker import (
    SoftwareChecker,
)


class OBSConfigurationChecker:
    """OBS を起動せず、既知の OBS config root の設定を確認する。"""

    _SECTION = "NDIPlugin"
    _KEY = "MainOutputEnabled"
    _WEBSOCKET_LEGACY_SECTION = "OBSWebSocket"
    _WEBSOCKET_LEGACY_KEYS = (
        "FirstLoad",
        "ServerEnabled",
        "ServerPort",
        "AlertsEnabled",
        "AuthRequired",
        "ServerPassword",
    )
    _WEBSOCKET_LEGACY_CONNECTION_KEYS = (
        "ServerEnabled",
        "ServerPort",
        "AuthRequired",
        "ServerPassword",
    )
    _PORTABLE_MARKERS = (
        "portable_mode",
        "obs_portable_mode",
        "portable_mode.txt",
        "obs_portable_mode.txt",
    )

    def __init__(
        self,
        obs_checker: SoftwareChecker,
        environment: EnvironmentPort,
        file_system: FileSystemPort,
        logger: LoggerPort,
    ) -> None:
        self._obs_checker = obs_checker
        self._environment = environment
        self._file_system = file_system
        self._logger = logger

    def check(self) -> OBSMainOutputCheckResult:
        """設定が有効、無効、または安全に確認できない状態を返す。"""
        try:
            obs_result = self._obs_checker.check()
            if (
                not obs_result.is_installed
                or obs_result.installation_path is None
            ):
                return self._unverified()

            configuration = self._configuration_context(
                obs_result.installation_path
            )
            if configuration is None:
                return self._unverified()
            user_base, global_ini = configuration

            user_ini = self._read_ini(user_base / "obs-studio" / "user.ini")
            values = [
                value
                for value in (
                    self._read_enabled_value(global_ini),
                    self._read_enabled_value(user_ini),
                )
                if value is not None
            ]
            if len(set(values)) > 1:
                # 設定移行時の優先順位は OBS/DistroAV の版で異なる。
                return self._unverified()

            result = OBSMainOutputCheckResult(
                status="enabled" if values and values[0] else "disabled"
            )
            self._logger.info(
                "OBS NDI Main Output configuration checked",
                status=result.status,
            )
            return result
        except Exception as exc:  # noqa: BLE001
            self._logger.warning(
                "OBS NDI Main Output configuration could not be checked",
                error_type=type(exc).__name__,
            )
            return self._unverified()

    def check_websocket(
        self, host: str, port: int, password: str
    ) -> OBSWebSocketCheckResult:
        """loopback接続先のOBS WebSocket保存値を、秘密値を返さず照合する。"""
        if not self._is_loopback_host(host):
            return OBSWebSocketCheckResult(status="not_applicable")

        try:
            obs_result = self._obs_checker.check()
            if (
                not obs_result.is_installed
                or obs_result.installation_path is None
            ):
                return self._websocket_unverified()
            module_config_base = self._default_config_base(
                obs_result.installation_path
            )
            if module_config_base is None:
                return self._websocket_unverified()
            legacy_values = self._read_legacy_websocket_config(
                module_config_base / "obs-studio" / "global.ini"
            )
            if legacy_values:
                legacy_settings = self._parse_legacy_websocket_settings(
                    legacy_values
                )
                if legacy_settings is None:
                    return self._websocket_unverified()
                return self._compare_websocket_settings(
                    *legacy_settings, port=port, password=password
                )

            config_path = (
                module_config_base
                / "obs-studio"
                / "plugin_config"
                / "obs-websocket"
                / "config.json"
            )
            config = self._read_json(config_path)
            if config is None:
                return self._websocket_unverified()

            enabled = config.get("server_enabled")
            if not isinstance(enabled, bool):
                return self._websocket_unverified()
            if not enabled:
                return OBSWebSocketCheckResult(status="disabled")

            saved_port = config.get("server_port")
            auth_required = config.get("auth_required")
            saved_password = config.get("server_password")
            if (
                not isinstance(saved_port, int)
                or isinstance(saved_port, bool)
                or not 1 <= saved_port <= 65535
                or not isinstance(auth_required, bool)
                or not isinstance(saved_password, str)
            ):
                return self._websocket_unverified()
            return self._compare_websocket_settings(
                enabled,
                saved_port,
                auth_required,
                saved_password,
                port=port,
                password=password,
            )
        except Exception as exc:  # noqa: BLE001
            self._logger.warning(
                "OBS WebSocket configuration could not be checked",
                error_type=type(exc).__name__,
            )
            return self._websocket_unverified()

    @staticmethod
    def _is_loopback_host(host: str) -> bool:
        normalized = host.strip().casefold()
        if normalized == "localhost":
            return True
        if normalized.startswith("[") and normalized.endswith("]"):
            normalized = normalized[1:-1]
        try:
            address = ipaddress.ip_address(normalized)
            if (
                isinstance(address, ipaddress.IPv6Address)
                and address.ipv4_mapped is not None
            ):
                address = address.ipv4_mapped
            return address.is_loopback
        except ValueError:
            return False

    def _configuration_context(
        self, obs_executable: Path
    ) -> tuple[Path, configparser.ConfigParser | None] | None:
        default_base = self._default_config_base(obs_executable)
        if default_base is None:
            return None
        global_ini = self._read_ini(default_base / "obs-studio" / "global.ini")
        # ポータブルモードでは OBS が Locations.Configuration を無視する。
        if global_ini is None or self._is_windows_portable(obs_executable):
            return default_base, global_ini
        user_base = self._user_config_base(
            global_ini, default_base, obs_executable
        )
        if user_base is None:
            return None
        return user_base, global_ini

    def _read_json(self, path: Path) -> dict[str, object] | None:
        if not self._file_system.exists(path):
            return None
        if not self._file_system.is_file(path):
            raise OSError("OBS WebSocket configuration is not a file")
        parsed: object = json.loads(
            self._file_system.read_bytes(path).decode("utf-8-sig")
        )
        return (
            cast(dict[str, object], parsed)
            if isinstance(parsed, dict)
            else None
        )

    def _read_legacy_websocket_config(
        self, path: Path
    ) -> dict[str, str | None]:
        if not self._file_system.exists(path):
            return {}
        if not self._file_system.is_file(path):
            raise OSError("OBS global configuration is not a file")
        text = self._file_system.read_bytes(path).decode("utf-8-sig")
        values: dict[str, str | None] = {}
        section = ""
        for line in text.splitlines():
            stripped = line.lstrip()
            if not stripped or stripped.startswith("#"):
                continue
            if stripped.startswith("["):
                closing_bracket = stripped.find("]")
                if closing_bracket >= 0:
                    section = stripped[1:closing_bracket]
                continue
            if section != self._WEBSOCKET_LEGACY_SECTION or "=" not in line:
                continue
            key, value = line.lstrip().split("=", 1)
            if key not in self._WEBSOCKET_LEGACY_KEYS:
                continue
            if key in values:
                values[key] = None
                continue
            values[key] = (
                None
                if "\x00" in value
                else self._unescape_obs_config_value(value)
            )
        return values

    @staticmethod
    def _unescape_obs_config_value(value: str) -> str:
        """OBS config-file.c の保存時 escape を読み戻す。"""
        unescaped: list[str] = []
        index = 0
        while index < len(value):
            char = value[index]
            if char == "\\" and index + 1 < len(value):
                escaped = value[index + 1]
                if escaped == "\\":
                    unescaped.append("\\")
                    index += 2
                    continue
                if escaped in {"r", "n"}:
                    unescaped.append("\r" if escaped == "r" else "\n")
                    index += 2
                    continue
            unescaped.append(char)
            index += 1
        return "".join(unescaped)

    @classmethod
    def _parse_legacy_websocket_settings(
        cls, values: dict[str, str | None]
    ) -> tuple[bool, int, bool, str] | None:
        raw = {
            key: values.get(key)
            for key in cls._WEBSOCKET_LEGACY_CONNECTION_KEYS
        }
        if any(value is None for value in raw.values()):
            return None
        enabled = cls._parse_obs_bool(raw["ServerEnabled"])
        port = cls._parse_obs_integer(raw["ServerPort"])
        auth_required = cls._parse_obs_bool(raw["AuthRequired"])
        password = raw["ServerPassword"]
        if (
            enabled is None
            or port is None
            or not 1 <= port <= 65535
            or auth_required is None
            or password is None
        ):
            return None
        return enabled, port, auth_required, password

    @classmethod
    def _parse_obs_bool(cls, value: str | None) -> bool | None:
        if value is None:
            return None
        normalized = value.casefold()
        if normalized == "true":
            return True
        if normalized == "false":
            return False
        integer = cls._parse_obs_integer(value)
        return None if integer is None else integer != 0

    @staticmethod
    def _parse_obs_integer(value: str | None) -> int | None:
        if value is None:
            return None
        normalized = value.strip()
        if normalized.startswith("0x"):
            digits = normalized[2:]
            if not digits or re.fullmatch(r"[0-9a-fA-F]+", digits) is None:
                return None
            return int(digits, 16)
        if re.fullmatch(r"[+-]?[0-9]+", normalized) is None:
            return None
        return int(normalized, 10)

    @staticmethod
    def _compare_websocket_settings(
        enabled: bool,
        saved_port: int,
        auth_required: bool,
        saved_password: str,
        *,
        port: int,
        password: str,
    ) -> OBSWebSocketCheckResult:
        if not enabled:
            return OBSWebSocketCheckResult(status="disabled")
        if saved_port != port:
            return OBSWebSocketCheckResult(status="port_mismatch")
        if auth_required and saved_password != password:
            return OBSWebSocketCheckResult(status="password_mismatch")
        return OBSWebSocketCheckResult(status="ready")

    def _websocket_unverified(self) -> OBSWebSocketCheckResult:
        result = OBSWebSocketCheckResult(status="unverified")
        self._logger.warning("OBS WebSocket configuration is unverified")
        return result

    def _default_config_base(self, obs_executable: Path) -> Path | None:
        if not obs_executable.is_absolute():
            return None
        if sys.platform == "darwin":
            home = self._environment.get("HOME")
            if not home:
                return None
            default_base = Path(home) / "Library" / "Application Support"
            obs_root = self._mac_bundle_root(obs_executable)
            if obs_root is None:
                return None
        elif sys.platform == "win32":
            app_data = self._environment.get("APPDATA")
            if not app_data:
                return None
            default_base = Path(app_data)
            obs_root = self._windows_install_root(obs_executable)
            if obs_root is None:
                return None
            if self._is_windows_portable(obs_executable):
                return obs_root / "config"
        else:
            return None

        if not default_base.is_absolute():
            return None
        return default_base

    @staticmethod
    def _mac_bundle_root(obs_executable: Path) -> Path | None:
        parents = obs_executable.parents
        if (
            len(parents) < 3
            or parents[0].name != "MacOS"
            or parents[1].name != "Contents"
            or not parents[2].name.endswith(".app")
        ):
            return None
        return parents[2]

    @staticmethod
    def _windows_install_root(obs_executable: Path) -> Path | None:
        parents = obs_executable.parents
        if (
            len(parents) < 3
            or parents[0].name.casefold() != "64bit"
            or parents[1].name.casefold() != "bin"
        ):
            return None
        return parents[2]

    def _user_config_base(
        self,
        global_ini: configparser.ConfigParser,
        default_base: Path,
        obs_executable: Path,
    ) -> Path | None:
        location = global_ini.get(
            "Locations", "Configuration", fallback=""
        ).strip()
        if not location:
            return default_base

        candidate = Path(location)
        if not candidate.is_absolute():
            if sys.platform == "darwin":
                # LaunchServices の相対パス基準はこの起動方法では特定できない。
                return None
            # Windows OBS は実行ファイルの親ディレクトリを作業ディレクトリにする。
            candidate = obs_executable.parent / candidate
        if self._file_system.exists(candidate):
            if self._file_system.is_dir(candidate):
                return candidate
            return None
        # 指定先が存在しない場合、OBS は既定の設定ルートを使う。
        return default_base

    def _is_windows_portable(self, obs_executable: Path) -> bool:
        if sys.platform != "win32":
            return False
        obs_root = self._windows_install_root(obs_executable)
        return obs_root is not None and any(
            self._file_system.exists(obs_root / marker)
            for marker in self._PORTABLE_MARKERS
        )

    def _read_ini(self, path: Path) -> configparser.ConfigParser | None:
        if not self._file_system.exists(path):
            return None
        if not self._file_system.is_file(path):
            raise OSError("OBS configuration is not a file")
        text = self._file_system.read_bytes(path).decode("utf-8-sig")
        parser = configparser.ConfigParser(interpolation=None)
        parser.read_string(text)
        return parser

    def _read_enabled_value(
        self, parser: configparser.ConfigParser | None
    ) -> bool | None:
        if parser is None or not parser.has_option(self._SECTION, self._KEY):
            return None
        return parser.getboolean(self._SECTION, self._KEY)

    def _unverified(self) -> OBSMainOutputCheckResult:
        result = OBSMainOutputCheckResult(status="unverified")
        self._logger.warning("OBS NDI Main Output configuration is unverified")
        return result
