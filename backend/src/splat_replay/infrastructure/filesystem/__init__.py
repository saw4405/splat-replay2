"""Filesystem infrastructure."""

from .paths import (
    ASSETS_DIR,
    CONFIG_DIR,
    IMAGE_MATCHING_FILE,
    PROJECT_ROOT,
    RUNTIME_ROOT,
    SETTINGS_FILE,
    THUMBNAIL_ASSETS_DIR,
    VIDEOS_DIR,
    asset,
    config,
    thumbnail_asset,
)

__all__ = [
    "PROJECT_ROOT",
    "RUNTIME_ROOT",
    "ASSETS_DIR",
    "CONFIG_DIR",
    "VIDEOS_DIR",
    "SETTINGS_FILE",
    "IMAGE_MATCHING_FILE",
    "THUMBNAIL_ASSETS_DIR",
    "asset",
    "config",
    "thumbnail_asset",
]
