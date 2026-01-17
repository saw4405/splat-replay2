"""Process related events."""

from dataclasses import dataclass
from typing import Literal

from .base import DomainEvent


EditUploadTrigger = Literal["auto", "manual"]


@dataclass(frozen=True, kw_only=True)
class EditUploadCompleted(DomainEvent):
    """編集・アップロード処理が完了したことを通知するイベント。"""

    EVENT_TYPE = "domain.process.edit_upload_completed"

    success: bool
    message: str
    trigger: EditUploadTrigger = "manual"


@dataclass(frozen=True, kw_only=True)
class AutoProcessPending(DomainEvent):
    """自動処理の開始待ち（キャンセル猶予中）イベント。"""

    EVENT_TYPE = "domain.process.pending"

    timeout_seconds: float
    message: str


@dataclass(frozen=True, kw_only=True)
class AutoProcessStarted(DomainEvent):
    """自動処理が実際に開始されたことを通知するイベント。"""

    EVENT_TYPE = "domain.process.started"


@dataclass(frozen=True, kw_only=True)
class AutoSleepPending(DomainEvent):
    """自動スリープの開始待ち（キャンセル猶予中）イベント。"""

    EVENT_TYPE = "domain.process.sleep.pending"

    timeout_seconds: float
    message: str


@dataclass(frozen=True, kw_only=True)
class AutoSleepStarted(DomainEvent):
    """自動スリープが実際に開始されたことを通知するイベント。"""

    EVENT_TYPE = "domain.process.sleep.started"
