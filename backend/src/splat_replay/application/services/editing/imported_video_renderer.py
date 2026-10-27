"""持込作業領域内で通常編集と同じ成果物を生成する。"""

from __future__ import annotations

from splat_replay.application.interfaces.thumbnail_design import (
    ThumbnailAssetsPort,
)

import asyncio
from datetime import date, time
from pathlib import Path

from splat_replay.application.interfaces import (
    ConfigPort,
    FileSystemPort,
    ImageSelector,
    LoggerPort,
    PathsPort,
    SubtitleEditorPort,
    TextToSpeechPort,
    ThumbnailRuleImageResolverPort,
    VideoEditorPort,
)
from splat_replay.application.interfaces.imported_video import (
    ImportedVideoRenderResult,
)
from splat_replay.domain.models import VideoAsset

from .subtitle_processor import SubtitleProcessor
from .thumbnail_generator import ThumbnailGenerator
from .title_description_generator import TitleDescriptionGenerator


class _StagedSubtitleWriter:
    """通常資産リポジトリを経由せず、対象動画の隣へ字幕を保存する。"""

    def __init__(self, file_system: FileSystemPort) -> None:
        self._file_system = file_system

    def save_edited_subtitle(self, video: Path, content: str) -> bool:
        self._file_system.write_text(video.with_suffix(".srt"), content)
        return True


class ImportedVideoRenderer:
    """結合済み持込動画へ編集設定を適用する。"""

    def __init__(
        self,
        logger: LoggerPort,
        config: ConfigPort,
        paths: PathsPort,
        video_editor: VideoEditorPort,
        subtitle_editor: SubtitleEditorPort,
        image_selector: ImageSelector,
        text_to_speech: TextToSpeechPort,
        rule_image_resolver: ThumbnailRuleImageResolverPort,
        file_system: FileSystemPort,
        thumbnail_assets: ThumbnailAssetsPort | None = None,
    ) -> None:
        self._config = config
        self._video_editor = video_editor
        self._file_system = file_system
        self.title_generator = TitleDescriptionGenerator(
            logger, config, video_editor
        )
        self.thumbnail_generator = ThumbnailGenerator(
            logger,
            paths,
            image_selector,
            file_system,
            rule_image_resolver,
            thumbnail_assets,
        )
        self.subtitle_processor = SubtitleProcessor(
            logger,
            config,
            subtitle_editor,
            text_to_speech,
            video_editor,
            _StagedSubtitleWriter(file_system),
            file_system,
        )

    async def render(
        self, target: Path, group: list[VideoAsset], day: date, time_slot: time
    ) -> ImportedVideoRenderResult:
        """通常キューへ登録せず、編集結果とsidecar内容を返す。"""
        await self.subtitle_processor.create_and_embed(target, group)
        title, description = await self.title_generator.generate(
            group, day, time_slot
        )
        thumbnail_path = await asyncio.to_thread(
            self.thumbnail_generator.create, group
        )
        thumbnail: bytes | None = None
        try:
            if thumbnail_path is not None and self._file_system.is_file(
                thumbnail_path
            ):
                thumbnail = await asyncio.to_thread(
                    self._file_system.read_bytes, thumbnail_path
                )
                await self._video_editor.embed_metadata_and_thumbnail(
                    target,
                    {"title": title, "description": description},
                    thumbnail,
                )
            else:
                await self._video_editor.embed_metadata(
                    target, {"title": title, "description": description}
                )
        finally:
            if thumbnail_path is not None:
                await asyncio.to_thread(
                    self._file_system.unlink, thumbnail_path, missing_ok=True
                )
        multiplier = self._config.get_video_edit_settings().volume_multiplier
        if multiplier != 1.0:
            await self._video_editor.change_volume(target, multiplier)
        subtitle_path = target.with_suffix(".srt")
        subtitle = (
            (
                await asyncio.to_thread(
                    self._file_system.read_bytes, subtitle_path
                )
            ).decode("utf-8")
            if self._file_system.is_file(subtitle_path)
            else None
        )
        return ImportedVideoRenderResult(
            title, description, thumbnail, subtitle
        )
