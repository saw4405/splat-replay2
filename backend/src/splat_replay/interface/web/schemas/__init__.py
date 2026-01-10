"""Web API schemas (DTOs).

Clean Architectureの原則に基づき、interface層のDTOを定義する。
これらはHTTPリクエスト/レスポンスの構造を表現する。
"""

from __future__ import annotations

from splat_replay.interface.web.schemas.common import (
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
    SubtitleBlock,
    SubtitleData,
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
    StepInfoResponse,
    SystemCheckResponse,
    VideoDeviceListResponse,
    YouTubePrivacyStatusRequest,
)

__all__ = [
    # Common
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
    "StepInfoResponse",
    "SystemCheckResponse",
    "VideoDeviceListResponse",
    "YouTubePrivacyStatusRequest",
]
