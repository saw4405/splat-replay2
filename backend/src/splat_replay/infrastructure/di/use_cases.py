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
from splat_replay.infrastructure.filesystem import RUNTIME_ROOT


def register_app_usecases(container: punq.Container) -> None:
    """アプリケーションのユースケースを DI コンテナに登録する。"""
    # Services
    container.register(
        SubtitleConverter, SubtitleConverter, scope=punq.Scope.singleton
    )

    container.register(AutoUseCase, AutoUseCase)
    container.register(UploadUseCase, UploadUseCase)

    # Assets Use Cases - runtime_root を注入する必要があるため factory で登録
    def list_recorded_videos_factory() -> ListRecordedVideosUseCase:
        return ListRecordedVideosUseCase(
            repository=container.resolve(VideoAssetRepositoryPort),
            logger=container.resolve(LoggerPort),
            runtime_root=RUNTIME_ROOT,
            video_editor=container.resolve(VideoEditorPort),
        )

    def delete_recorded_video_factory() -> DeleteRecordedVideoUseCase:
        return DeleteRecordedVideoUseCase(
            repository=container.resolve(VideoAssetRepositoryPort),
            logger=container.resolve(LoggerPort),
            runtime_root=RUNTIME_ROOT,
        )

    def list_edited_videos_factory() -> ListEditedVideosUseCase:
        return ListEditedVideosUseCase(
            repository=container.resolve(VideoAssetRepositoryPort),
            logger=container.resolve(LoggerPort),
            runtime_root=RUNTIME_ROOT,
            video_editor=container.resolve(VideoEditorPort),
        )

    def delete_edited_video_factory() -> DeleteEditedVideoUseCase:
        return DeleteEditedVideoUseCase(
            repository=container.resolve(VideoAssetRepositoryPort),
            logger=container.resolve(LoggerPort),
            runtime_root=RUNTIME_ROOT,
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

    # Metadata Use Cases - runtime_root を注入する必要があるため factory で登録
    def update_recorded_metadata_factory() -> UpdateRecordedMetadataUseCase:
        return UpdateRecordedMetadataUseCase(
            repository=container.resolve(VideoAssetRepositoryPort),
            logger=container.resolve(LoggerPort),
            runtime_root=RUNTIME_ROOT,
            video_editor=container.resolve(VideoEditorPort),
        )

    def get_recorded_subtitle_structured_factory() -> (
        GetRecordedSubtitleStructuredUseCase
    ):
        return GetRecordedSubtitleStructuredUseCase(
            repository=container.resolve(VideoAssetRepositoryPort),
            logger=container.resolve(LoggerPort),
            runtime_root=RUNTIME_ROOT,
            converter=container.resolve(SubtitleConverter),
        )

    def update_recorded_subtitle_structured_factory() -> (
        UpdateRecordedSubtitleStructuredUseCase
    ):
        return UpdateRecordedSubtitleStructuredUseCase(
            repository=container.resolve(VideoAssetRepositoryPort),
            logger=container.resolve(LoggerPort),
            runtime_root=RUNTIME_ROOT,
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
