"""Web API schemas (DTOs).

Clean Architectureの原則に基づき、interface層のDTOを定義する。
これらはHTTPリクエスト/レスポンスの構造を表現する。
"""

from __future__ import annotations

from splat_replay.interface.web.schemas.common import (
    EditUploadProcessOptionsUpdateRequest,
    EditUploadState,
    EditUploadStatus,
    EditUploadTriggerResponse,
)
from splat_replay.interface.web.schemas.editing import (
    EditedVideoItem,
    RecordedVideoItem,
)
from splat_replay.interface.web.schemas.metadata import (
    MetadataOptionItem,
    MetadataOptionsResponse,
    MetadataUpdateRequest,
    RecordingMetadataResponse,
    RecordingMetadataUpdateRequest,
    SubtitleBlock,
    SubtitleData,
)
from splat_replay.interface.web.schemas.history import (
    BattleHistoryItem,
    BattleHistoryResponse,
)
from splat_replay.interface.web.schemas.settings import (
    SettingsUpdateRequest,
    SettingsUpdateSection,
)
from splat_replay.interface.web.schemas.setup import (
    CaptureDeviceRequest,
    ErrorResponse,
    InstallationStatusResponse,
    MessageResponse,
    OBSConfigResponse,
    OBSWebSocketPasswordRequest,
    MicrophoneDeviceListResponse,
    StepInfoResponse,
    SystemCheckResponse,
    VideoDeviceListResponse,
    YouTubePrivacyStatusRequest,
)

__all__ = [
    # Common
    "EditUploadProcessOptionsUpdateRequest",
    "EditUploadState",
    "EditUploadStatus",
    "EditUploadTriggerResponse",
    # Editing
    "EditedVideoItem",
    "RecordedVideoItem",
    # Metadata
    "MetadataOptionItem",
    "MetadataOptionsResponse",
    "MetadataUpdateRequest",
    "RecordingMetadataResponse",
    "RecordingMetadataUpdateRequest",
    "SubtitleBlock",
    "SubtitleData",
    # Settings
    "SettingsUpdateRequest",
    "SettingsUpdateSection",
    # Setup
    "CaptureDeviceRequest",
    "ErrorResponse",
    "InstallationStatusResponse",
    "MessageResponse",
    "OBSConfigResponse",
    "OBSWebSocketPasswordRequest",
    "MicrophoneDeviceListResponse",
    "StepInfoResponse",
    "SystemCheckResponse",
    "VideoDeviceListResponse",
    "YouTubePrivacyStatusRequest",
    # History
    "BattleHistoryItem",
    "BattleHistoryResponse",
]
