"""Capture-device enumeration and connectivity adapters."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from typing import Any

from structlog.stdlib import BoundLogger

from splat_replay.application.interfaces import (
    CaptureDeviceDescriptor,
    CaptureDeviceEnumeratorPort,
    CaptureDevicePort,
    CaptureDeviceSettingsView,
)

_INSTANCE_PREFIX = "@device_pnp_\\\\?\\"
_HARDWARE_ID_PATTERN = re.compile(
    r"^(?P<hardware_id>[^\\]+\\VID_[0-9A-F]{4}&PID_[0-9A-F]{4})",
    flags=re.IGNORECASE,
)
_USBMI_SUFFIX_PATTERN = re.compile(r"#USBMI\(\d+\)$", flags=re.IGNORECASE)


def _normalize_instance_id(instance_id: str | None) -> str | None:
    if instance_id is None:
        return None
    normalized = instance_id.strip()
    if not normalized:
        return None
    return normalized.upper()


def _normalize_location_path(location_path: str | None) -> str | None:
    if location_path is None:
        return None
    normalized = location_path.strip()
    if not normalized:
        return None
    normalized = _USBMI_SUFFIX_PATTERN.sub("", normalized)
    return normalized.upper()


def _derive_hardware_id(pnp_instance_id: str | None) -> str | None:
    if pnp_instance_id is None:
        return None
    match = _HARDWARE_ID_PATTERN.match(pnp_instance_id)
    if match is None:
        return None
    return match.group("hardware_id").upper()


def _extract_quoted_value(line: str) -> str | None:
    start = line.find('"')
    end = line.rfind('"')
    if start == -1 or end == -1 or start >= end:
        return None
    value = line[start + 1 : end].strip()
    return value or None


def _extract_pnp_instance_id(alternative_name: str | None) -> str | None:
    if not alternative_name:
        return None
    normalized = alternative_name.strip()
    if not normalized.lower().startswith(_INSTANCE_PREFIX.lower()):
        return None
    value = normalized[len(_INSTANCE_PREFIX) :]
    value = value.split("#{", 1)[0]
    value = value.split("\\global", 1)[0]
    value = value.replace("#", "\\")
    return _normalize_instance_id(value)


def _select_location_path(location_paths: list[str]) -> str | None:
    normalized = [
        candidate
        for candidate in (
            _normalize_location_path(location_path)
            for location_path in location_paths
        )
        if candidate is not None
    ]
    if not normalized:
        return None
    normalized.sort(
        key=lambda candidate: (candidate.count("#"), len(candidate))
    )
    return normalized[0]


def _powershell_json(command: str, timeout: float = 10) -> Any:
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", command],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        creationflags=subprocess.CREATE_NO_WINDOW
        if sys.platform == "win32"
        else 0,
        check=False,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return None
    return json.loads(result.stdout)


def _query_pnp_metadata(
    pnp_instance_id: str | None, logger: BoundLogger
) -> tuple[str | None, str | None]:
    if sys.platform != "win32" or pnp_instance_id is None:
        return None, None

    escaped_instance_id = pnp_instance_id.replace("'", "''")
    command = (
        "$ErrorActionPreference='Stop';"
        f"$instanceId='{escaped_instance_id}';"
        "$props=Get-PnpDeviceProperty -InstanceId $instanceId -ErrorAction Stop;"
        "$locationPaths=@("
        "$props | Where-Object KeyName -eq 'DEVPKEY_Device_LocationPaths' "
        "| Select-Object -ExpandProperty Data -ErrorAction SilentlyContinue"
        ");"
        "$parent=($props | Where-Object KeyName -eq 'DEVPKEY_Device_Parent' "
        "| Select-Object -First 1 -ExpandProperty Data -ErrorAction SilentlyContinue);"
        "[pscustomobject]@{"
        "location_paths=@($locationPaths);"
        "parent_instance_id=$parent"
        "} | ConvertTo-Json -Compress"
    )

    try:
        payload = _powershell_json(command)
    except FileNotFoundError:
        logger.warning("PowerShell not found while resolving PnP metadata")
        return None, None
    except subprocess.TimeoutExpired:
        logger.warning(
            "PnP metadata query timed out", instance_id=pnp_instance_id
        )
        return None, None
    except Exception as exc:
        logger.warning(
            "Failed to resolve PnP metadata",
            instance_id=pnp_instance_id,
            error=str(exc),
        )
        return None, None

    if not isinstance(payload, dict):
        return None, None

    raw_location_paths = payload.get("location_paths")
    location_paths = (
        [str(value) for value in raw_location_paths]
        if isinstance(raw_location_paths, list)
        else []
    )
    parent_instance_id = payload.get("parent_instance_id")
    normalized_parent = _normalize_instance_id(
        str(parent_instance_id) if parent_instance_id else None
    )
    return _select_location_path(location_paths), normalized_parent


def _build_descriptor(
    name: str, alternative_name: str | None, logger: BoundLogger
) -> CaptureDeviceDescriptor:
    pnp_instance_id = _extract_pnp_instance_id(alternative_name)
    hardware_id = _derive_hardware_id(pnp_instance_id)
    location_path, parent_instance_id = _query_pnp_metadata(
        pnp_instance_id, logger
    )
    return CaptureDeviceDescriptor(
        name=name,
        alternative_name=alternative_name,
        pnp_instance_id=pnp_instance_id,
        hardware_id=hardware_id,
        location_path=location_path,
        parent_instance_id=parent_instance_id,
    )


def _get_video_device_descriptors_from_ffmpeg(
    logger: BoundLogger, timeout: float = 10
) -> list[CaptureDeviceDescriptor]:
    """Enumerate DirectShow video devices together with PnP metadata."""
    try:
        result = subprocess.run(
            [
                "ffmpeg",
                "-list_devices",
                "true",
                "-f",
                "dshow",
                "-i",
                "dummy",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            creationflags=subprocess.CREATE_NO_WINDOW
            if sys.platform == "win32"
            else 0,
            check=False,
        )
    except FileNotFoundError:
        logger.error(
            "FFmpeg not found. Please install FFmpeg to list video devices."
        )
        return []
    except subprocess.TimeoutExpired:
        logger.error("FFmpeg device enumeration timed out")
        return []
    except Exception as exc:
        logger.error("Failed to enumerate video devices", error=str(exc))
        return []

    pending_name: str | None = None
    pending_alternative_name: str | None = None
    descriptors: list[CaptureDeviceDescriptor] = []

    for line in result.stderr.splitlines():
        if "(video)" in line and '"' in line:
            if pending_name is not None:
                descriptors.append(
                    _build_descriptor(
                        pending_name, pending_alternative_name, logger
                    )
                )
            pending_name = _extract_quoted_value(line)
            pending_alternative_name = None
            continue

        if "Alternative name" in line and pending_name is not None:
            pending_alternative_name = _extract_quoted_value(line)

    if pending_name is not None:
        descriptors.append(
            _build_descriptor(pending_name, pending_alternative_name, logger)
        )

    return descriptors


def _find_descriptor_match(
    settings: CaptureDeviceSettingsView,
    descriptors: list[CaptureDeviceDescriptor],
) -> CaptureDeviceDescriptor | None:
    normalized_hardware_id = (
        settings.hardware_id.upper() if settings.hardware_id else None
    )
    normalized_location_path = _normalize_location_path(settings.location_path)
    if normalized_hardware_id and normalized_location_path:
        for descriptor in descriptors:
            if (
                descriptor.hardware_id == normalized_hardware_id
                and descriptor.location_path == normalized_location_path
            ):
                return descriptor
        return None

    matched_by_name = [
        descriptor
        for descriptor in descriptors
        if descriptor.name == settings.name
    ]
    if len(matched_by_name) == 1:
        return matched_by_name[0]
    return None


class CaptureDeviceChecker(CaptureDevicePort):
    """Check whether the configured capture device is currently connected."""

    def __init__(
        self,
        settings: CaptureDeviceSettingsView,
        logger: BoundLogger,
    ) -> None:
        self._settings = settings
        self.logger = logger

    def update_settings(self, settings: CaptureDeviceSettingsView) -> None:
        self._settings = settings
        self.logger.info(
            "Capture device settings updated",
            device_name=settings.name,
        )

    def is_connected(self) -> bool:
        if sys.platform != "win32":
            self.logger.warning("Check skipped (not Windows)")
            return True

        descriptors = _get_video_device_descriptors_from_ffmpeg(self.logger)
        return _find_descriptor_match(self._settings, descriptors) is not None


class CaptureDeviceEnumerator(CaptureDeviceEnumeratorPort):
    """List available capture devices."""

    def __init__(self, logger: BoundLogger) -> None:
        self.logger = logger

    def list_video_devices(self) -> list[str]:
        if sys.platform != "win32":
            self.logger.warning("Device enumeration skipped (not Windows)")
            return []

        descriptors = self.list_video_device_descriptors()
        seen: set[str] = set()
        devices: list[str] = []
        for descriptor in descriptors:
            if descriptor.name in seen:
                continue
            seen.add(descriptor.name)
            devices.append(descriptor.name)
        self.logger.info("Video devices enumerated", count=len(devices))
        return devices

    def list_video_device_descriptors(self) -> list[CaptureDeviceDescriptor]:
        if sys.platform != "win32":
            self.logger.warning("Device enumeration skipped (not Windows)")
            return []

        descriptors = _get_video_device_descriptors_from_ffmpeg(self.logger)
        self.logger.info(
            "Video device descriptors enumerated",
            count=len(descriptors),
        )
        return descriptors
