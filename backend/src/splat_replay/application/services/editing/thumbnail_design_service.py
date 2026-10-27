"""デザイン編集の素材管理と共通レンダラによる見本生成。"""

from splat_replay.application.interfaces.thumbnail_design import (
    ThumbnailAssetsPort,
    ThumbnailAssetInfo,
    ThumbnailBounds,
)
from splat_replay.application.services.editing.thumbnail_generator import (
    ThumbnailGenerator,
)
from splat_replay.domain.config.video_edit import ThumbnailDesign


class ThumbnailDesignService:
    def __init__(
        self, assets: ThumbnailAssetsPort, generator: ThumbnailGenerator
    ) -> None:
        self.assets = assets
        self.generator = generator

    def catalog(self) -> list[ThumbnailAssetInfo]:
        return self.assets.catalog()

    def default_design(self) -> ThumbnailDesign:
        return self.assets.default_design()

    def preview(self, design: ThumbnailDesign, scenario: str) -> bytes:
        return self.preview_with_layout(design, scenario)[0]

    def preview_with_layout(
        self, design: ThumbnailDesign, scenario: str
    ) -> tuple[bytes, dict[str, ThumbnailBounds]]:
        layout: dict[str, ThumbnailBounds] = {}
        with self.assets.sample(scenario) as samples:
            result = self.generator.create(samples, design, layout)
            if result is None:
                raise ValueError("サンプル画像を生成できませんでした")
            return self.assets.read(result), layout

    def upload(self, content: bytes) -> str:
        return self.assets.upload(content)

    def delete(self, asset_id: str, draft: ThumbnailDesign) -> None:
        self.assets.delete(asset_id, draft)
