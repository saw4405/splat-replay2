from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import (
    Awaitable,
    Callable,
    Iterable,
    List,
    Literal,
    Optional,
    Protocol,
    Tuple,
    TypeVar,
    Union,
)

from splat_replay.domain.models import Frame, RecordingMetadata, VideoAsset

PrivacyStatus = Literal["public", "private", "unlisted"]

RecorderStatus = Literal["started", "paused", "resumed", "stopped"]


@dataclass
class Caption:
    subtitle: Path
    caption_name: str
    language: str = "ja"


class CaptureDevicePort(Protocol):
    """キャプチャデバイスの接続確認を行うポート。"""

    def is_connected(self) -> bool: ...


class CapturePort(Protocol):
    """キャプチャデバイスからの映像を取得するポート。"""

    def init(self) -> None: ...

    def capture(self) -> Optional[Frame]: ...

    def close(self) -> None: ...


class RecorderWithTranscriptionPort(Protocol):
    """録画を制御するアウトバウンドポート。"""

    async def init(self) -> None: ...

    async def start(self) -> None: ...

    async def stop(self) -> Tuple[Optional[Path], Optional[Path]]: ...

    async def pause(self) -> None: ...

    async def resume(self) -> None: ...

    async def cancel(self) -> None: ...

    async def close(self) -> None: ...

    def add_status_listener(
        self, listener: Callable[[RecorderStatus], Awaitable[None]]
    ) -> None: ...

    def remove_status_listener(
        self, listener: Callable[[RecorderStatus], Awaitable[None]]
    ) -> None: ...


class VideoRecorderPort(Protocol):
    """録画を制御するアウトバウンドポート。"""

    async def init(self) -> None: ...

    async def start(self) -> None: ...

    async def stop(self) -> Optional[Path]: ...

    async def pause(self) -> None: ...

    async def resume(self) -> None: ...

    async def close(self) -> None: ...

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


class VideoAssetRepository(Protocol):
    """動画ファイルを保存・管理するポート."""

    def save_recording(
        self,
        video: Path,
        srt: Path | None,
        screenshot: Frame | None,
        metadata: RecordingMetadata,
    ) -> VideoAsset: ...

    def list_recordings(self) -> list[VideoAsset]: ...

    def delete_recording(self, video: Path) -> None: ...

    def save_edited(self, video: Path) -> Path: ...

    def list_edited(self) -> list[Path]: ...

    def delete_edited(self, video: Path) -> None: ...


class VideoEditorPort(Protocol):
    """動画編集処理を提供するポート。"""

    def merge(self, clips: list[Path], output: Path) -> Path: ...

    def embed_metadata(self, path: Path, metadata: dict[str, str]): ...

    def get_metadata(self, path: Path) -> dict[str, str]: ...

    def embed_subtitle(self, path: Path, srt: str): ...

    def get_subtitle(self, path: Path) -> Optional[str]: ...

    def embed_thumbnail(self, path: Path, thumbnail: bytes): ...

    def get_thumbnail(self, path: Path) -> Optional[bytes]: ...

    def change_volume(self, path: Path, multiplier: float): ...

    def get_video_length(self, path: Path) -> Optional[float]: ...


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
        *args,
        **kwargs,
    ) -> ImageDrawerPort: ...

    T = TypeVar("T")

    def for_each(
        self,
        iterable: Iterable[T],
        fn: Callable[[T, ImageDrawerPort], ImageDrawerPort],
    ) -> ImageDrawerPort: ...

    def save(self, path: Path): ...

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
        playlist_id: Optional[str] = None,
    ): ...


class AuthenticatedClientPort(Protocol):
    """認証済みのクライアントを提供するポート。"""

    def authenticate(self) -> None: ...


class PowerPort(Protocol):
    """電源制御を行うポート。"""

    async def sleep(self) -> None: ...
