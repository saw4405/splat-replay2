"""ユースケースが依存するポート定義。"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from splat_replay.domain.models.match import Match


class VideoRecorder(Protocol):
    """録画を制御するアウトバウンドポート。"""

    def start(self) -> None: ...

    def stop(self) -> Path: ...

    def pause(self) -> None: ...

    def resume(self) -> None: ...


class VideoEditorPort(Protocol):
    """動画編集処理を提供するポート。"""

    def process(self, path: Path) -> Path: ...


class UploadPort(Protocol):
    """動画アップロード処理を提供するポート。"""

    def upload(self, path: Path) -> str: ...


class PowerPort(Protocol):
    """電源制御を行うポート。"""

    def sleep(self) -> None: ...


class ScreenAnalyzerPort(Protocol):
    """画面解析処理を提供するポート。"""

    def detect_battle_start(self, frame: Path) -> bool: ...

    def detect_loading(self, frame: Path) -> bool: ...

    def detect_loading_end(self, frame: Path) -> bool: ...

    def detect_result(self, frame: Path) -> bool: ...

    def detect_power_off(self) -> bool: ...


class SpeechTranscriberPort(Protocol):
    """音声文字起こし処理を提供するポート。"""

    def start_capture(self) -> None: ...

    def stop_capture(self) -> Path: ...

    def transcribe(self, audio: Path) -> str: ...


class MetadataExtractorPort(Protocol):
    """動画からメタデータを抽出するポート。"""

    def extract_from_video(self, path: Path) -> "Match": ...
