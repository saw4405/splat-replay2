"""サムネイル素材の永続化と、生成中の素材保護の境界。"""

from contextlib import AbstractContextManager
from pathlib import Path
from typing import Protocol, TypedDict

from splat_replay.domain.config.video_edit import ThumbnailDesign
from splat_replay.domain.models import VideoAsset


class ThumbnailAssetInfo(TypedDict):
    id: str
    name: str
    kind: str
    protected: bool


class ThumbnailBounds(TypedDict):
    x: int
    y: int
    width: int
    height: int


class ThumbnailAssetsPort(Protocol):
    def guard(self) -> AbstractContextManager[None]: ...
    def lease(
        self, design: ThumbnailDesign | None = None
    ) -> AbstractContextManager[ThumbnailDesign]: ...
    def default_design(self) -> ThumbnailDesign: ...
    def validate_references(self, design: ThumbnailDesign) -> None: ...
    def catalog(self) -> list[ThumbnailAssetInfo]: ...
    def upload(self, content: bytes) -> str: ...
    def delete(self, asset_id: str, draft: ThumbnailDesign) -> None: ...
    def path(self, asset_id: str) -> Path: ...
    def sample(
        self, scenario: str
    ) -> AbstractContextManager[list[VideoAsset]]: ...
    def read(self, path: Path) -> bytes: ...
