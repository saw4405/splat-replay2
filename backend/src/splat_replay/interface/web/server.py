"""Web API Server - 共通サービスの集約。"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from splat_replay.application.interfaces import EventBusPort
from splat_replay.application.services import (
    AutoRecorder,
    DeviceChecker,
    ErrorHandler,
    ProgressEventStore,
    RecordingPreparationService,
    SetupService,
    SystemCheckService,
    SystemSetupService,
)
from splat_replay.application.services.common.settings_service import (
    SettingsService,
)
from splat_replay.application.services.process.auto_process_service import (
    AutoProcessService,
)
from splat_replay.application.use_cases import (
    AutoRecordingUseCase,
    UploadUseCase,
)
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
from splat_replay.interface.web.error_handler import WebErrorHandler
from structlog.stdlib import BoundLogger


class WebAPIServer:
    """WebAPIServer - Web API用の共通サービスを集約。

    責務：
    - 共通サービス（Settings/Setup/System）の保持
    - パス情報（project_root/runtime_root）の保持
    - Use Case の保持
    """

    settings_service: SettingsService
    setup_service: SetupService
    system_check_service: SystemCheckService
    system_setup_service: SystemSetupService
    error_handler: ErrorHandler
    web_error_handler: WebErrorHandler
    logger: BoundLogger
    device_checker: DeviceChecker
    recording_preparation_service: RecordingPreparationService
    upload_use_case: UploadUseCase
    auto_recording_use_case_factory: Callable[[], AutoRecordingUseCase]
    auto_recorder: AutoRecorder
    auto_process_service: AutoProcessService
    progress_store: ProgressEventStore
    event_bus: EventBusPort
    project_root: Path
    runtime_root: Path
    base_dir: Path
    assets_dir: Path

    # Assets Use Cases
    list_recorded_videos_uc: ListRecordedVideosUseCase
    delete_recorded_video_uc: DeleteRecordedVideoUseCase
    list_edited_videos_uc: ListEditedVideosUseCase
    delete_edited_video_uc: DeleteEditedVideoUseCase
    get_edit_upload_status_uc: GetEditUploadStatusUseCase
    start_edit_upload_uc: StartEditUploadUseCase

    # Metadata Use Cases
    update_recorded_metadata_uc: UpdateRecordedMetadataUseCase
    get_recorded_subtitle_structured_uc: GetRecordedSubtitleStructuredUseCase
    update_recorded_subtitle_structured_uc: (
        UpdateRecordedSubtitleStructuredUseCase
    )

    def __init__(
        self,
        settings_service: SettingsService,
        setup_service: SetupService,
        system_check_service: SystemCheckService,
        system_setup_service: SystemSetupService,
        error_handler: ErrorHandler,
        logger: BoundLogger,
        device_checker: DeviceChecker,
        recording_preparation_service: RecordingPreparationService,
        upload_use_case: UploadUseCase,
        auto_recording_use_case_factory: Callable[[], AutoRecordingUseCase],
        auto_recorder: AutoRecorder,
        auto_process_service: AutoProcessService,
        progress_store: ProgressEventStore,
        event_bus: EventBusPort,
        project_root: Path,
        runtime_root: Path,
        base_dir: Path,
        assets_dir: Path,
        # Assets Use Cases
        list_recorded_videos_uc: ListRecordedVideosUseCase,
        delete_recorded_video_uc: DeleteRecordedVideoUseCase,
        list_edited_videos_uc: ListEditedVideosUseCase,
        delete_edited_video_uc: DeleteEditedVideoUseCase,
        get_edit_upload_status_uc: GetEditUploadStatusUseCase,
        start_edit_upload_uc: StartEditUploadUseCase,
        # Metadata Use Cases
        update_recorded_metadata_uc: UpdateRecordedMetadataUseCase,
        get_recorded_subtitle_structured_uc: GetRecordedSubtitleStructuredUseCase,
        update_recorded_subtitle_structured_uc: UpdateRecordedSubtitleStructuredUseCase,
    ) -> None:
        """初期化。

        Args:
            settings_service: 設定サービス
            setup_service: セットアップサービス
            system_check_service: システムチェックサービス
            system_setup_service: システムセットアップサービス
            error_handler: エラーハンドラー
            logger: ロガー
            device_checker: デバイスチェッカー
            recording_preparation_service: 録画準備サービス
            upload_use_case: アップロードユースケース
            auto_recording_use_case_factory: 自動録画ユースケースファクトリ
            auto_recorder: 自動録画サービス
            auto_process_service: 自動処理サービス
            progress_store: 進捗イベントストア
            event_bus: イベントバス
            project_root: プロジェクトルートディレクトリ
            runtime_root: ランタイムルートディレクトリ
            base_dir: 録画ファイル保存先ディレクトリ
            assets_dir: アセットディレクトリ
            list_recorded_videos_uc: 録画一覧取得ユースケース
            delete_recorded_video_uc: 録画削除ユースケース
            list_edited_videos_uc: 編集済み一覧取得ユースケース
            delete_edited_video_uc: 編集済み削除ユースケース
            get_edit_upload_status_uc: 編集アップロード状態取得ユースケース
            start_edit_upload_uc: 編集アップロード開始ユースケース
            update_recorded_metadata_uc: メタデータ更新ユースケース
            get_recorded_subtitle_structured_uc: 構造化字幕取得ユースケース
            update_recorded_subtitle_structured_uc: 構造化字幕更新ユースケース
        """
        self.settings_service = settings_service
        self.setup_service = setup_service
        self.system_check_service = system_check_service
        self.system_setup_service = system_setup_service
        self.error_handler = error_handler
        self.web_error_handler = WebErrorHandler(logger)
        self.logger = logger
        self.device_checker = device_checker
        self.recording_preparation_service = recording_preparation_service
        self.upload_use_case = upload_use_case
        self.auto_recording_use_case_factory = auto_recording_use_case_factory
        self.auto_recorder = auto_recorder
        self.auto_process_service = auto_process_service
        self.progress_store = progress_store
        self.event_bus = event_bus
        self.project_root = project_root
        self.runtime_root = runtime_root
        self.base_dir = base_dir
        self.assets_dir = assets_dir

        # Assets Use Cases
        self.list_recorded_videos_uc = list_recorded_videos_uc
        self.delete_recorded_video_uc = delete_recorded_video_uc
        self.list_edited_videos_uc = list_edited_videos_uc
        self.delete_edited_video_uc = delete_edited_video_uc
        self.get_edit_upload_status_uc = get_edit_upload_status_uc
        self.start_edit_upload_uc = start_edit_upload_uc

        # Metadata Use Cases
        self.update_recorded_metadata_uc = update_recorded_metadata_uc
        self.get_recorded_subtitle_structured_uc = (
            get_recorded_subtitle_structured_uc
        )
        self.update_recorded_subtitle_structured_uc = (
            update_recorded_subtitle_structured_uc
        )


__all__ = ["WebAPIServer"]
