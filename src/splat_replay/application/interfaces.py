from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Any,
    Awaitable,
    Callable,
    Iterable,
    List,
    Literal,
    Mapping,
    Optional,
    Protocol,
    Tuple,
    TypeVar,
    Union,
)

from splat_replay.domain.models import Frame, RecordingMetadata, VideoAsset

if TYPE_CHECKING:
    from splat_replay.shared.config import CaptureDeviceSettings, OBSSettings

PrivacyStatus = Literal["public", "private", "unlisted"]

RecorderStatus = Literal["started", "paused", "resumed", "stopped"]


@dataclass
class Caption:
    subtitle: Path
    caption_name: str
    language: str = "ja"


SpeechAudioEncoding = Literal["LINEAR16", "MP3", "OGG_OPUS"]


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


class TextToSpeechPort(Protocol):
    """テキスト読み上げ処理を提供するポート。"""

    def synthesize(
        self, request: SpeechSynthesisRequest
    ) -> SpeechSynthesisResult: ...


class CaptureDevicePort(Protocol):
    """キャプチャデバイスの接続確認を行うポート。"""

    def update_settings(self, settings: CaptureDeviceSettings) -> None: ...

    def is_connected(self) -> bool: ...


class CapturePort(Protocol):
    """キャプチャデバイスからの映像を取得するポート。"""

    def setup(self) -> None: ...

    def capture(self) -> Optional[Frame]: ...

    def teardown(self) -> None: ...


class RecorderWithTranscriptionPort(Protocol):
    """録画を制御するアウトバウンドポート。"""

    async def setup(self) -> None: ...

    async def start(self) -> None: ...

    async def stop(self) -> Tuple[Optional[Path], Optional[Path]]: ...

    async def pause(self) -> None: ...

    async def resume(self) -> None: ...

    async def cancel(self) -> None: ...

    async def teardown(self) -> None: ...

    def add_status_listener(
        self, listener: Callable[[RecorderStatus], Awaitable[None]]
    ) -> None: ...

    def remove_status_listener(
        self, listener: Callable[[RecorderStatus], Awaitable[None]]
    ) -> None: ...


class VideoRecorderPort(Protocol):
    """録画を制御するアウトバウンドポート。"""

    def update_settings(self, settings: OBSSettings) -> None: ...

    async def setup(self) -> None: ...

    async def start(self) -> None: ...

    async def stop(self) -> Optional[Path]: ...

    async def pause(self) -> None: ...

    async def resume(self) -> None: ...

    async def teardown(self) -> None: ...

    def add_status_listener(
        self, listener: Callable[[RecorderStatus], Awaitable[None]]
    ) -> None: ...

    def remove_status_listener(
        self, listener: Callable[[RecorderStatus], Awaitable[None]]
    ) -> None: ...


class SpeechTranscriberPort(Protocol):
    """音声文字起こし処理を提供するポート。"""

    def start(self) -> None: ...

    def stop(self) -> str: ...

    def pause(self) -> None: ...

    def resume(self) -> None: ...


class VideoAssetRepositoryPort(Protocol):
    """動画ファイルを保存・管理するポート."""

    def get_recorded_dir(self) -> Path: ...

    def get_edited_dir(self) -> Path: ...

    def save_recording(
        self,
        video: Path,
        srt: Path | None,
        screenshot: Frame | None,
        metadata: RecordingMetadata,
    ) -> VideoAsset: ...

    def get_asset(self, video: Path) -> VideoAsset | None: ...

    def save_edited_metadata(
        self, video: Path, metadata: RecordingMetadata
    ) -> None: ...

    def list_recordings(self) -> list[VideoAsset]: ...

    def delete_recording(self, video: Path) -> bool: ...

    def get_subtitle(self, video: Path) -> Optional[str]: ...

    def save_subtitle(self, video: Path, content: str) -> bool: ...

    def save_edited(self, video: Path) -> Path: ...

    def list_edited(self) -> list[Path]: ...

    def delete_edited(self, video: Path) -> bool: ...

    def get_edited_subtitle(self, video: Path) -> Optional[str]: ...

    def save_edited_subtitle(self, video: Path, content: str) -> bool: ...

    def get_edited_thumbnail(self, video: Path) -> Optional[bytes]: ...

    def save_edited_thumbnail(self, video: Path, data: bytes) -> bool: ...

    def get_edited_metadata(self, video: Path) -> Optional[dict[str, str]]: ...

    def save_edited_metadata_dict(
        self, video: Path, metadata: dict[str, str]
    ) -> bool: ...


class VideoEditorPort(Protocol):
    """動画編集処理を提供するポート。"""

    async def merge(self, clips: list[Path], output: Path) -> Path: ...

    async def embed_metadata(
        self, path: Path, metadata: dict[str, str]
    ) -> None: ...

    async def get_metadata(self, path: Path) -> dict[str, str]: ...

    async def embed_subtitle(self, path: Path, srt: str) -> None: ...

    async def get_subtitle(self, path: Path) -> Optional[str]: ...

    async def embed_thumbnail(self, path: Path, thumbnail: bytes) -> None: ...

    async def get_thumbnail(self, path: Path) -> Optional[bytes]: ...

    async def change_volume(self, path: Path, multiplier: float) -> None: ...

    async def get_video_length(self, path: Path) -> Optional[float]: ...

    async def add_audio_track(
        self,
        path: Path,
        audio: Path,
        *,
        stream_title: Optional[str] = None,
    ) -> None: ...


Color = Union[str, Tuple[int, ...]]


class ImageDrawerPort(Protocol):
    """画像描画処理を提供するポート。"""

    @staticmethod
    def select_brightest_image(
        paths: List[Path], target_rect: Tuple[float, float, float, float]
    ) -> Optional[ImageDrawerPort]: ...

    def when(
        self,
        flag: bool,
        fn: Callable[..., ImageDrawerPort],
        /,
        *args: object,
        **kwargs: object,
    ) -> ImageDrawerPort: ...

    T = TypeVar("T")

    def for_each(
        self,
        iterable: Iterable[T],
        fn: Callable[[T, ImageDrawerPort], ImageDrawerPort],
    ) -> ImageDrawerPort: ...

    def save(self, path: Path) -> None: ...

    def draw_rectangle(
        self,
        rect: Tuple[int, int, int, int],
        fill_color: Color | None,
        outline_color: Color | None,
        outline_width: int,
    ) -> ImageDrawerPort: ...

    def draw_rounded_rectangle(
        self,
        rect: Tuple[int, int, int, int],
        radius: int,
        fill_color: Color | None,
        outline_color: Color | None,
        outline_width: int,
    ) -> ImageDrawerPort: ...

    def draw_text(
        self,
        text: str,
        position: Tuple[int, int],
        font_name: str,
        font_size: int,
        fill_color: Color,
    ) -> ImageDrawerPort: ...

    def draw_text_with_outline(
        self,
        text: str,
        position: Tuple[int, int],
        font_name: str,
        font_size: int,
        fill_color: Color,
        outline_color: Color,
        outline_width: int,
        center: bool = False,
    ) -> ImageDrawerPort: ...

    def draw_image(
        self,
        path: Path,
        position: Tuple[int, int],
        crop: Optional[Tuple[int, int, int, int]] = None,
        size: Optional[Tuple[int, int]] = None,
    ) -> ImageDrawerPort: ...

    def overlay_image(self, path: Path) -> ImageDrawerPort: ...


ImageSelector = Callable[
    [List[Path], Tuple[float, float, float, float]], ImageDrawerPort
]


class SubtitleEditorPort(Protocol):
    """字幕編集処理を提供するポート。"""

    def merge(
        self, subtitles: List[Path], video_length: List[float]
    ) -> str: ...


class UploadPort(Protocol):
    """動画アップロード処理を提供するポート。"""

    def upload(
        self,
        path: Path,
        title: str,
        description: str,
        tags: List[str] = [],
        privacy_status: PrivacyStatus = "private",
        thumb: Optional[Path] = None,
        caption: Optional[Caption] = None,
        playlist_id: str = "",
    ) -> None: ...


class AuthenticatedClientPort(Protocol):
    """認証済みのクライアントを提供するポート。"""

    def authenticate(self) -> None: ...


class PowerPort(Protocol):
    """電源制御を行うポート。"""

    async def sleep(self) -> None: ...


class EventPublisher(Protocol):
    def publish(
        self, event_type: str, payload: Mapping[str, Any] | None = None
    ) -> None: ...


class FramePublisher(Protocol):
    def publish_frame(self, frame: "Frame") -> None: ...


class CommandDispatcher(Protocol):
    def submit(
        self, name: str, **payload: Any
    ) -> Any: ...  # returns Future-like


class EventSubscription(Protocol):
    def poll(self, max_items: int = 100) -> Any: ...  # returns list[Event]
    def close(self) -> None: ...


class EventSubscriber(Protocol):
    def subscribe(
        self, event_types: Optional[set[str]] = None
    ) -> EventSubscription: ...


class FrameSource(Protocol):
    def add_listener(self, cb: Callable[[Frame], None]) -> None: ...
    def remove_listener(self, cb: Callable[[Frame], None]) -> None: ...
    def get_latest(self) -> Optional[Frame]: ...


@dataclass(frozen=True)
class CommandResult:
    """コマンド実行結果。"""

    return_code: int
    stdout: str
    stderr: str

    @property
    def success(self) -> bool:
        """コマンドが成功したかどうか。"""
        return self.return_code == 0


class CommandExecutionError(Exception):
    """コマンド実行エラー。"""

    def __init__(
        self,
        message: str,
        command: list[str],
        cause: Optional[Exception] = None,
    ) -> None:
        """エラーを初期化する。

        Args:
            message: エラーメッセージ
            command: 実行しようとしたコマンド
            cause: 原因となった例外（オプション）
        """
        super().__init__(message)
        self.command = command
        self.cause = cause


class SystemCommandPort(Protocol):
    """システムコマンド実行のポートインターフェース。"""

    def execute_command(
        self,
        command: list[str],
        timeout: Optional[float] = None,
    ) -> CommandResult: ...

    def check_command_exists(self, command: str) -> bool: ...
