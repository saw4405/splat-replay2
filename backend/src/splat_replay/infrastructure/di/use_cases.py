"""DI Container: Use cases registration.

Phase 3 リファクタリング - ユースケースの登録を分離。
"""

from __future__ import annotations

import punq

from splat_replay.application.interfaces import (
    LoggerPort,
    VideoAssetRepositoryPort,
    VideoEditorPort,
)
from splat_replay.application.services.common import SubtitleConverter
from splat_replay.application.use_cases import AutoUseCase, UploadUseCase
from splat_replay.application.use_cases.assets import (
    DeleteEditedVideoUseCase,
    DeleteRecordedVideoUseCase,
    GetEditUploadStatusUseCase,
    ListEditedVideosUseCase,
    ListRecordedVideosUseCase,
    StartEditUploadUseCase,
)
from splat_replay.application.use_cases.metadata import (
    GetRecordedSubtitleStructuredUseCase,
    UpdateRecordedMetadataUseCase,
    UpdateRecordedSubtitleStructuredUseCase,
)
from splat_replay.domain.config import AppSettings


def register_app_usecases(container: punq.Container) -> None:
    """アプリケーションのユースケースを DI コンテナに登録する。"""
    # Services
    container.register(
        SubtitleConverter, SubtitleConverter, scope=punq.Scope.singleton
    )

    container.register(AutoUseCase, AutoUseCase)
    container.register(UploadUseCase, UploadUseCase)

    # Assets Use Cases - base_dir を注入する必要があるため factory で登録
    app_settings = container.resolve(AppSettings)
    base_dir = app_settings.storage.base_dir

    def list_recorded_videos_factory() -> ListRecordedVideosUseCase:
        return ListRecordedVideosUseCase(
            repository=container.resolve(VideoAssetRepositoryPort),
            logger=container.resolve(LoggerPort),
            base_dir=base_dir,
            video_editor=container.resolve(VideoEditorPort),
        )

    def delete_recorded_video_factory() -> DeleteRecordedVideoUseCase:
        return DeleteRecordedVideoUseCase(
            repository=container.resolve(VideoAssetRepositoryPort),
            logger=container.resolve(LoggerPort),
            base_dir=base_dir,
        )

    def list_edited_videos_factory() -> ListEditedVideosUseCase:
        return ListEditedVideosUseCase(
            repository=container.resolve(VideoAssetRepositoryPort),
            logger=container.resolve(LoggerPort),
            base_dir=base_dir,
            video_editor=container.resolve(VideoEditorPort),
        )

    def delete_edited_video_factory() -> DeleteEditedVideoUseCase:
        return DeleteEditedVideoUseCase(
            repository=container.resolve(VideoAssetRepositoryPort),
            logger=container.resolve(LoggerPort),
            base_dir=base_dir,
        )

    container.register(
        ListRecordedVideosUseCase, factory=list_recorded_videos_factory
    )
    container.register(
        DeleteRecordedVideoUseCase, factory=delete_recorded_video_factory
    )
    container.register(
        ListEditedVideosUseCase, factory=list_edited_videos_factory
    )
    container.register(
        DeleteEditedVideoUseCase, factory=delete_edited_video_factory
    )
    container.register(GetEditUploadStatusUseCase, GetEditUploadStatusUseCase)
    container.register(StartEditUploadUseCase, StartEditUploadUseCase)

    # Metadata Use Cases - base_dir を注入する必要があるため factory で登録
    def update_recorded_metadata_factory() -> UpdateRecordedMetadataUseCase:
        return UpdateRecordedMetadataUseCase(
            repository=container.resolve(VideoAssetRepositoryPort),
            logger=container.resolve(LoggerPort),
            base_dir=base_dir,
            video_editor=container.resolve(VideoEditorPort),
        )

    def get_recorded_subtitle_structured_factory() -> (
        GetRecordedSubtitleStructuredUseCase
    ):
        return GetRecordedSubtitleStructuredUseCase(
            repository=container.resolve(VideoAssetRepositoryPort),
            logger=container.resolve(LoggerPort),
            base_dir=base_dir,
            converter=container.resolve(SubtitleConverter),
        )

    def update_recorded_subtitle_structured_factory() -> (
        UpdateRecordedSubtitleStructuredUseCase
    ):
        return UpdateRecordedSubtitleStructuredUseCase(
            repository=container.resolve(VideoAssetRepositoryPort),
            logger=container.resolve(LoggerPort),
            base_dir=base_dir,
            converter=container.resolve(SubtitleConverter),
        )

    container.register(
        UpdateRecordedMetadataUseCase, factory=update_recorded_metadata_factory
    )
    container.register(
        GetRecordedSubtitleStructuredUseCase,
        factory=get_recorded_subtitle_structured_factory,
    )
    container.register(
        UpdateRecordedSubtitleStructuredUseCase,
        factory=update_recorded_subtitle_structured_factory,
    )
