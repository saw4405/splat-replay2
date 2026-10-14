"""DI Container: Configuration registration.

Phase 3 リファクタリング - 設定値の登録を分離。
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import punq

from splat_replay.application.interfaces import (
    BehaviorSettingsView,
    CaptureDeviceSettingsView,
    OBSSettingsView,
    SpeechSettingsView,
    SpeechTranscriberSettingsView,
    UploadSettingsView,
    VideoEditSettingsView,
)
from splat_replay.domain.config import (
    AppSettings,
    BehaviorSettings,
    CaptureDeviceSettings,
    ImageMatchingSettings,
    OBSSettings,
    RecordSettings,
    RemoteAccessSettings,
    SpeechTranscriberSettings,
    UploadSettings,
    VideoEditSettings,
    VideoStorageSettings,
)
from splat_replay.infrastructure.config import load_settings_from_toml
from splat_replay.infrastructure.filesystem import paths
from splat_replay.infrastructure.logging import get_logger

_NO_EXPECTATION = object()


def _write_bytes_atomically(
    path: Path,
    content: bytes,
    *,
    expected_current: bytes | None | object = _NO_EXPECTATION,
) -> bool:
    """一時ファイルから原子的に置き換え、必要なら直前に現状を再確認する。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=path.parent,
            prefix=f"{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            temporary_file.write(content)
            temporary_file.flush()
        if expected_current is not _NO_EXPECTATION:
            try:
                current_content = path.read_bytes()
            except FileNotFoundError:
                current_content = None
            if current_content != expected_current:
                return False
        temporary_path.replace(path)
        temporary_path = None
        return True
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError as exc:
                get_logger().warning(
                    "一時画像マッチング設定ファイルの削除に失敗しました",
                    path=str(temporary_path),
                    error=str(exc),
                )


def _sync_bundled_image_matching_settings(
    current_path: Path, bundled_path: Path
) -> None:
    """未編集の保存済み既定設定だけをbundle版へ更新する。"""
    logger = get_logger()
    baseline_path = current_path.with_name(f"{current_path.name}.baseline")

    try:
        bundled_content = bundled_path.read_bytes()
    except OSError as exc:
        logger.warning(
            "同梱画像マッチング設定を読み込めません",
            path=str(bundled_path),
            error=str(exc),
        )
        return

    try:
        current_content = current_path.read_bytes()
    except FileNotFoundError:
        current_content = None
    except OSError as exc:
        logger.warning(
            "保存済み画像マッチング設定の比較に失敗しました",
            path=str(current_path),
            error=str(exc),
        )
        return

    if current_content is None:
        try:
            current_copied = _write_bytes_atomically(
                current_path, bundled_content, expected_current=None
            )
            if not current_copied:
                return
            _write_bytes_atomically(baseline_path, bundled_content)
        except OSError as exc:
            logger.warning(
                "同梱画像マッチング設定の初期同期に失敗しました",
                path=str(current_path),
                error=str(exc),
            )
        return

    if current_content == bundled_content:
        try:
            _write_bytes_atomically(baseline_path, bundled_content)
        except OSError as exc:
            logger.warning(
                "画像マッチング設定のbaseline保存に失敗しました",
                path=str(baseline_path),
                error=str(exc),
            )
        return

    try:
        baseline_content = baseline_path.read_bytes()
    except FileNotFoundError:
        return
    except OSError as exc:
        logger.warning(
            "画像マッチング設定baselineの比較に失敗しました",
            path=str(baseline_path),
            error=str(exc),
        )
        return

    if current_content != baseline_content:
        return

    try:
        ImageMatchingSettings.load_from_yaml(bundled_path)
    except Exception as exc:
        logger.warning(
            "新しい同梱画像マッチング設定の検証に失敗しました",
            path=str(bundled_path),
            error=str(exc),
        )
        return

    try:
        current_updated = _write_bytes_atomically(
            current_path,
            bundled_content,
            expected_current=current_content,
        )
        if not current_updated:
            return
        _write_bytes_atomically(baseline_path, bundled_content)
    except OSError as exc:
        logger.warning(
            "画像マッチング設定の更新に失敗しました",
            path=str(current_path),
            error=str(exc),
        )


def register_config(container: punq.Container) -> AppSettings:
    """設定を DI コンテナに登録する。"""
    settings = load_settings_from_toml()
    container.register(BehaviorSettings, instance=settings.behavior)
    container.register(BehaviorSettingsView, instance=settings.behavior)
    container.register(CaptureDeviceSettings, instance=settings.capture_device)
    container.register(
        CaptureDeviceSettingsView, instance=settings.capture_device
    )
    container.register(OBSSettings, instance=settings.obs)
    container.register(OBSSettingsView, instance=settings.obs)
    container.register(RecordSettings, instance=settings.record)
    container.register(RemoteAccessSettings, instance=settings.remote_access)
    container.register(
        SpeechTranscriberSettings, instance=settings.speech_transcriber
    )
    container.register(
        SpeechSettingsView, instance=settings.speech_transcriber
    )
    container.register(
        SpeechTranscriberSettingsView, instance=settings.speech_transcriber
    )
    container.register(VideoStorageSettings, instance=settings.storage)
    container.register(VideoEditSettings, instance=settings.video_edit)
    container.register(VideoEditSettingsView, instance=settings.video_edit)
    container.register(UploadSettings, instance=settings.upload)
    container.register(UploadSettingsView, instance=settings.upload)
    return settings


def register_image_matching_settings(
    container: punq.Container, path: Path | None = None
) -> ImageMatchingSettings:
    """画像マッチング設定を DI コンテナに登録する。"""
    if path is None:
        path = paths.IMAGE_MATCHING_FILE
        bundled_path = paths.PROJECT_ROOT / "config" / "image_matching.yaml"
        if paths.IS_MACOS_FROZEN and bundled_path.is_file():
            _sync_bundled_image_matching_settings(path, bundled_path)
    if not path.exists():
        raise FileNotFoundError(
            f"画像マッチング設定ファイルが見つかりません: {path}"
        )
    image_settings = ImageMatchingSettings.load_from_yaml(path)
    container.register(ImageMatchingSettings, instance=image_settings)
    return image_settings
