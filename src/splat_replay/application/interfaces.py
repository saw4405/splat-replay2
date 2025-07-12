"""ユースケースが依存するポート定義。"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

import numpy as np
import speech_recognition as sr

from splat_replay.domain.models import (
    GameMode,
    RateBase,
    Result,
    RecordingMetadata,
    VideoAsset,
)
from splat_replay.domain.models.play import Play


class VideoRecorder(Protocol):
    """録画を制御するアウトバウンドポート。"""

    def start(self) -> None: ...

    def stop(self) -> Path: ...

    def pause(self) -> None: ...

    def resume(self) -> None: ...


class SpeechRecognizerPort(Protocol):
    """音声認識処理を提供するポート。"""

    def recognize(self, audio: sr.AudioData) -> str | None: ...


class SpeechTranscriberPort(Protocol):
    """音声文字起こし処理を提供するポート。"""

    def start(self) -> None: ...

    def stop(self) -> str: ...

    def pause(self) -> None: ...

    def resume(self) -> None: ...


class VideoEditorPort(Protocol):
    """動画編集処理を提供するポート。"""

    def process(self, assets: list[VideoAsset]) -> list[Path]: ...


class UploadPort(Protocol):
    """動画アップロード処理を提供するポート。"""

    def upload(self, path: Path) -> str: ...


class PowerPort(Protocol):
    """電源制御を行うポート。"""

    def sleep(self) -> None: ...


class FrameAnalyzerPort(Protocol):
    """フレーム解析処理を提供するポート。"""

    def set_mode(self, mode: GameMode) -> None: ...

    def reset(self) -> None: ...

    def detect_match_select(self, frame: np.ndarray) -> bool: ...

    def extract_rate(self, frame: np.ndarray) -> RateBase | None: ...

    def detect_matching_start(self, frame: np.ndarray) -> bool: ...

    def detect_schedule_change(self, frame: np.ndarray) -> bool: ...

    def detect_battle_start(self, frame: np.ndarray) -> bool: ...

    def detect_battle_abort(self, frame: np.ndarray) -> bool: ...

    def detect_loading(self, frame: np.ndarray) -> bool: ...

    def detect_loading_end(self, frame: np.ndarray) -> bool: ...

    def detect_battle_finish(self, frame: np.ndarray) -> bool: ...

    def detect_battle_finish_end(self, frame: np.ndarray) -> bool: ...

    def detect_battle_judgement(self, frame: np.ndarray) -> bool: ...

    def extract_battle_judgement(self, frame: np.ndarray) -> str | None: ...

    def detect_battle_result(self, frame: np.ndarray) -> bool: ...

    def extract_battle_result(self, frame: np.ndarray) -> Result | None: ...

    def detect_power_off(self, frame: np.ndarray) -> bool: ...


class MetadataExtractorPort(Protocol):
    """動画からメタデータを抽出するポート。"""

    def extract_from_video(self, path: Path) -> "Play": ...


class CaptureDevicePort(Protocol):
    """キャプチャデバイスの接続確認を行うポート。"""

    def is_connected(self) -> bool: ...


class OBSControlPort(VideoRecorder, Protocol):
    """OBS Studio の状態を制御するポート。"""

    def is_running(self) -> bool: ...

    def launch(self) -> None: ...

    def is_connected(self) -> bool: ...

    def connect(self) -> None: ...

    def start_virtual_camera(self) -> None: ...

    def is_virtual_camera_active(self) -> bool: ...


class VideoAssetRepository(Protocol):
    """動画ファイルを保存・管理するポート."""

    def save_recording(
        self,
        video: Path,
        subtitle: str,
        screenshot: np.ndarray | None,
        metadata: RecordingMetadata,
    ) -> VideoAsset: ...

    def list_recordings(self) -> list[VideoAsset]: ...

    def save_edited(self, video: Path) -> Path: ...

    def list_edited(self) -> list[Path]: ...
