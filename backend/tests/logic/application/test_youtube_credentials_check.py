"""YouTube client JSON の検証と秘密値の非露出を守る。"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from unittest.mock import MagicMock

import pytest

from splat_replay.application.interfaces import (
    EnvironmentPort,
    FileSystemPort,
    LoggerPort,
    OBSConfigurationCheckerPort,
    PathsPort,
    ThumbnailFontResolverPort,
)
from splat_replay.application.services.setup.system_check_service import (
    SystemCheckService,
)
from splat_replay.application.services.system.software_checker import (
    SoftwareChecker,
)


class _MemoryFileSystem:
    def __init__(self, path: Path, content: bytes | None) -> None:
        self.path = path
        self.content = content

    def is_file(self, path: Path) -> bool:
        return path == self.path and self.content is not None

    def read_bytes(self, path: Path) -> bytes:
        if path != self.path or self.content is None:
            raise FileNotFoundError
        return self.content


def _system_check_service(
    config_dir: Path, file_system: _MemoryFileSystem, logger: MagicMock
) -> SystemCheckService:
    checker = cast(SoftwareChecker, MagicMock())
    return SystemCheckService(
        obs_checker=checker,
        ffmpeg_checker=checker,
        tesseract_checker=checker,
        flac_checker=checker,
        ndi_checker=checker,
        font_resolver=cast(ThumbnailFontResolverPort, MagicMock()),
        paths=cast(
            PathsPort,
            SimpleNamespace(get_config_dir=lambda: config_dir),
        ),
        file_system=cast(FileSystemPort, file_system),
        environment=cast(EnvironmentPort, MagicMock()),
        logger=cast(LoggerPort, logger),
        distroav_checker=checker,
        obs_configuration_checker=cast(
            OBSConfigurationCheckerPort, MagicMock()
        ),
    )


@pytest.mark.parametrize("profile", ["installed", "web"])
def test_youtube_credentials_accepts_valid_installed_or_web_profile(
    tmp_path: Path, profile: str
) -> None:
    secret = "SENSITIVE-CREDENTIAL-DATA"
    content = json.dumps(
        {
            profile: {
                "client_id": "client-id",
                "client_secret": secret,
                "auth_uri": "https://accounts.example/auth",
                "token_uri": "https://accounts.example/token",
            }
        }
    ).encode()
    logger = MagicMock()
    service = _system_check_service(
        tmp_path,
        _MemoryFileSystem(tmp_path / "client_secret.json", content),
        logger,
    )

    result = service.check_youtube_credentials()

    assert result.is_installed is True
    assert secret not in repr(result)
    assert secret not in repr(logger.mock_calls)


def test_youtube_credentials_rejects_missing_required_value(
    tmp_path: Path,
) -> None:
    secret = "SENSITIVE-CREDENTIAL-DATA"
    content = json.dumps(
        {
            "installed": {
                "client_id": "client-id",
                "client_secret": secret,
                "auth_uri": "https://accounts.example/auth",
            }
        }
    ).encode()
    service = _system_check_service(
        tmp_path,
        _MemoryFileSystem(tmp_path / "client_secret.json", content),
        MagicMock(),
    )

    result = service.check_youtube_credentials()

    assert result.is_installed is False
    assert secret not in repr(result)


def test_youtube_credentials_rejects_malformed_json_without_logging_content(
    tmp_path: Path,
) -> None:
    secret = "SENSITIVE-CREDENTIAL-DATA"
    logger = MagicMock()
    service = _system_check_service(
        tmp_path,
        _MemoryFileSystem(
            tmp_path / "client_secret.json",
            f'{{"client_secret":"{secret}"'.encode(),
        ),
        logger,
    )

    result = service.check_youtube_credentials()

    assert result.is_installed is False
    assert secret not in repr(result)
    assert secret not in repr(logger.mock_calls)
