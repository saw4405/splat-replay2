"""API レスポンスおよびリクエスト用スキーマ定義。"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class RecorderAction(str, Enum):
    """録画制御で利用可能なアクション。"""

    START = "start"
    PAUSE = "pause"
    RESUME = "resume"
    STOP = "stop"
    CANCEL = "cancel"


class RecorderStateResponse(BaseModel):
    """録画状態と監視タスク状態のレスポンス。"""

    state: str = Field(
        ..., description="StateMachine が保持する現在の録画状態"
    )
    loop_running: bool = Field(
        ..., description="自動録画監視タスクが動作中かどうか"
    )


class OperationResponse(BaseModel):
    """単純な操作結果レスポンス。"""

    status: str = Field(
        ...,
        description="accepted / already_running / stopped / error などの状態",
    )
    message: str | None = Field(default=None, description="補足メッセージ")


class VideoAssetResponse(BaseModel):
    """録画済み動画情報。"""

    asset_id: str = Field(
        ..., description="ファイルパスをエンコードした内部 ID"
    )
    video_path: str = Field(..., description="動画ファイルの絶対パス")
    subtitle_path: str | None = Field(
        default=None, description="字幕ファイルの絶対パス"
    )
    thumbnail_path: str | None = Field(
        default=None, description="サムネイル画像の絶対パス"
    )
    length_seconds: float | None = Field(
        default=None, description="動画の再生時間（秒）"
    )
    metadata: dict[str, str | None] | None = Field(
        default=None, description="RecordingMetadata を辞書化したもの"
    )


class EditedAssetResponse(BaseModel):
    """編集済み動画情報。"""

    asset_id: str = Field(
        ..., description="ファイルパスをエンコードした内部 ID"
    )
    video_path: str = Field(..., description="編集済み動画の絶対パス")
    length_seconds: float | None = Field(
        default=None, description="再生時間（秒）"
    )
    metadata: dict[str, str | None] | None = Field(
        default=None, description="埋め込まれたメタデータ"
    )


class AssetMetadataUpdate(BaseModel):
    """メタデータ更新リクエストボディ。"""

    metadata: dict[str, str | None] = Field(
        ..., description="保存対象のメタデータ辞書"
    )


class EventResponse(BaseModel):
    """イベントログの 1 行。"""

    id: str = Field(..., description="イベント ID")
    type: str = Field(..., description="イベント種別")
    timestamp: float = Field(..., description="イベント発生時刻 (epoch 秒)")
    severity: str = Field(..., description="ログレベル相当の重要度")
    payload: dict[str, Any] = Field(..., description="付帯情報")
    correlation_id: str | None = Field(
        default=None, description="関連イベント識別子 (存在する場合)"
    )


class BehaviorSettingsResponse(BaseModel):
    """挙動設定のレスポンス。"""

    edit_after_power_off: bool = Field(
        ..., description="電源オフ後に自動編集・アップロードを行うか"
    )
    sleep_after_upload: bool = Field(
        ..., description="アップロード完了後にスリープするか"
    )


class BehaviorSettingsUpdate(BehaviorSettingsResponse):
    """挙動設定更新リクエスト。"""

    pass


__all__ = [
    "RecorderAction",
    "RecorderStateResponse",
    "OperationResponse",
    "VideoAssetResponse",
    "EditedAssetResponse",
    "AssetMetadataUpdate",
    "EventResponse",
    "BehaviorSettingsResponse",
    "BehaviorSettingsUpdate",
]
