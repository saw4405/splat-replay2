"""Data types and TypedDict definitions for settings and requests."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import (
    Any,
    List,
    Literal,
    NotRequired,
    Optional,
    Protocol,
    Required,
    TypedDict,
)

from pydantic import SecretStr

# Type aliases
PrivacyStatus = Literal["public", "private", "unlisted"]
SpeechAudioEncoding = Literal["LINEAR16", "MP3", "OGG_OPUS"]


# Settings View Protocols


class BehaviorSettingsView(Protocol):
    """Behavior settings shape exposed to application use cases."""

    edit_after_power_off: bool
    sleep_after_upload: bool


class UploadSettingsView(Protocol):
    """Upload settings shape exposed to application services."""

    privacy_status: PrivacyStatus
    tags: list[str]
    playlist_id: str
    caption_name: str


class SpeechSettingsView(Protocol):
    """Speech settings shape used by video edit workflow."""

    enabled: bool
    language_code: str
    voice_name: str
    speaking_rate: float
    pitch: float
    audio_encoding: SpeechAudioEncoding
    sample_rate_hz: int
    model: str
    track_title: str


class VideoEditSettingsView(Protocol):
    """Video edit settings shape exposed to application services."""

    volume_multiplier: float
    title_template: str
    description_template: str
    chapter_template: str
    speech: SpeechSettingsView


class CaptureDeviceSettingsView(Protocol):
    """Capture device settings shape passed to hardware ports."""

    name: str


class SecretString(Protocol):
    """Secret string abstraction to avoid tying to concrete secrets type."""

    def get_secret_value(self) -> str: ...


class OBSSettingsView(Protocol):
    """OBS settings shape passed to recorder ports."""

    websocket_host: str
    websocket_port: int
    websocket_password: SecretStr
    executable_path: Path


# TypedDict definitions for settings UI


class SettingFieldData(TypedDict):
    id: Required[str]
    label: Required[str]
    description: Required[str]
    type: Required[str]
    recommended: Required[bool]
    user_editable: NotRequired[bool]
    value: NotRequired[Any]
    choices: NotRequired[List[str]]
    children: NotRequired[List["SettingFieldData"]]


class SettingSectionData(TypedDict):
    id: Required[str]
    label: Required[str]
    fields: Required[List[SettingFieldData]]


class SectionUpdate(TypedDict):
    id: str
    values: dict[str, Any]


# Request/Response dataclasses


@dataclass(frozen=True)
class SpeechSynthesisRequest:
    """読み上げ生成リクエスト。"""

    text: str
    language_code: str
    voice_name: str
    speaking_rate: float
    pitch: float
    audio_encoding: SpeechAudioEncoding
    sample_rate_hz: int
    model: Optional[str] = None


@dataclass(frozen=True)
class SpeechSynthesisResult:
    """読み上げ生成結果。"""

    audio: bytes
    sample_rate_hz: int


@dataclass(frozen=True)
class FileStats:
    """ファイルの統計情報。"""

    size_bytes: int
    updated_at: float


@dataclass
class Caption:
    """Video caption metadata."""

    subtitle: Path
    caption_name: str
    language: str = "ja"


class SettingsRepositoryPort(Protocol):
    """設定値のメタ情報と保存を扱うポート。"""

    def fetch_sections(self) -> List[SettingSectionData]: ...

    def update_sections(self, updates: List[SectionUpdate]) -> None: ...
