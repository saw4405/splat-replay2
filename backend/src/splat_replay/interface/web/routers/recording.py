"""録画制御ルーター。

責務：
- 録画準備（OBS起動・仮想カメラ有効化）
- 録画開始・一時停止・再開・停止
- 録画状態の取得
- リアルタイムメタデータの取得・保存
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from splat_replay.interface.web.server import WebAPIServer


# ========================================
# Response Schemas
# ========================================


class StandardResponse(BaseModel):
    """標準レスポンススキーマ。"""

    success: bool = Field(description="操作が成功したかどうか")
    error: str | None = Field(None, description="エラーメッセージ（失敗時）")
    state: str | None = Field(None, description="自動録画の状態")


class RecorderStateResponse(BaseModel):
    """録画状態レスポンススキーマ。"""

    state: str = Field(description="録画状態 (STOPPED / RECORDING / PAUSED)")


class PreviewFrameResponse(BaseModel):
    """プレビューフレームレスポンススキーマ。"""

    has_frame: bool = Field(description="フレームが利用可能かどうか")
    image_data_url: str | None = Field(
        None, description="Data URL 形式の画像データ"
    )
    timestamp: float | None = Field(
        None, description="フレームのタイムスタンプ (UNIX 時間)"
    )


class RecordingMetadataResponse(BaseModel):
    """録画メタデータレスポンススキーマ。"""

    game_mode: str | None = Field(None, description="ゲームモード")
    stage_name: str | None = Field(None, description="ステージ名")
    stage: str | None = Field(None, description="ステージ")
    result: str | None = Field(None, description="結果")
    my_weapon: str | None = Field(None, description="自分の武器")
    started_at: str | None = Field(None, description="開始時刻")
    match: str | None = Field(None, description="マッチ")
    rule: str | None = Field(None, description="ルール")
    rate: str | None = Field(None, description="レート")
    judgement: str | None = Field(None, description="判定")
    kill: int | None = Field(None, description="キル数")
    death: int | None = Field(None, description="デス数")
    special: int | None = Field(None, description="スペシャル数")


class RecordingMetadataUpdateRequest(BaseModel):
    """録画メタデータ更新リクエストスキーマ。"""

    game_mode: str | None = None
    stage_name: str | None = None
    stage: str | None = None
    result: str | None = None
    my_weapon: str | None = None
    started_at: str | None = None
    match: str | None = None
    rule: str | None = None
    rate: str | None = None
    judgement: str | None = None
    kill: int | None = None
    death: int | None = None
    special: int | None = None


def create_recording_router(server: WebAPIServer) -> APIRouter:
    """録画制御ルーターを作成。

    Args:
        server: WebAPIServerインスタンス

    Returns:
        設定済みのAPIRouter
    """
    router = APIRouter(prefix="/api/recorder", tags=["recording"])

    @router.post("/prepare", response_model=StandardResponse)
    async def prepare_recording() -> StandardResponse:
        """録画準備（OBS起動・仮想カメラ有効化）。"""
        try:
            await server.recording_preparation_service.prepare_recording()
            return StandardResponse(success=True)
        except Exception as e:
            server.logger.error("録画準備エラー", error=str(e))
            return StandardResponse(success=False, error=str(e))

    @router.post("/enable-auto", response_model=StandardResponse)
    async def enable_auto_recording() -> StandardResponse:
        """自動録画モードを有効化（バトル開始検知開始）。"""
        try:
            use_case = server.auto_recording_use_case_factory()
            started = await use_case.start_background()
            if not started:
                return StandardResponse(
                    success=False,
                    error="already_running",
                    state=use_case.status(),
                )
            return StandardResponse(success=True, state=use_case.status())
        except Exception as e:
            server.logger.error("自動録画有効化エラー", error=str(e))
            return StandardResponse(success=False, error=str(e))

    @router.post("/start", response_model=StandardResponse)
    async def manual_start_recorder() -> StandardResponse:
        """手動録画開始。"""
        try:
            await server.auto_recorder.start()
            return StandardResponse(success=True)
        except Exception as e:
            server.logger.error("手動録画開始エラー", error=str(e))
            return StandardResponse(success=False, error=str(e))

    @router.post("/pause", response_model=StandardResponse)
    async def manual_pause_recorder() -> StandardResponse:
        """手動録画一時停止。"""
        try:
            await server.auto_recorder.pause()
            return StandardResponse(success=True)
        except Exception as e:
            server.logger.error("手動録画一時停止エラー", error=str(e))
            return StandardResponse(success=False, error=str(e))

    @router.post("/resume", response_model=StandardResponse)
    async def manual_resume_recorder() -> StandardResponse:
        """手動録画再開。"""
        try:
            await server.auto_recorder.resume()
            return StandardResponse(success=True)
        except Exception as e:
            server.logger.error("手動録画再開エラー", error=str(e))
            return StandardResponse(success=False, error=str(e))

    @router.post("/stop", response_model=StandardResponse)
    async def manual_stop_recorder() -> StandardResponse:
        """手動録画停止。"""
        try:
            await server.auto_recorder.stop()
            return StandardResponse(success=True)
        except Exception as e:
            server.logger.error("手動録画停止エラー", error=str(e))
            return StandardResponse(success=False, error=str(e))

    @router.get("/state", response_model=RecorderStateResponse)
    async def get_recorder_state() -> RecorderStateResponse:
        """録画状態取得。"""
        state = server.auto_recorder.get_state()
        return RecorderStateResponse(state=state)

    @router.get("/metadata", response_model=RecordingMetadataResponse)
    async def get_recording_metadata() -> RecordingMetadataResponse:
        """リアルタイム録画メタデータ取得。

        現在録画中のメタデータ（ステージ、ルール、キルデス等）を取得する。
        """
        # TODO: AutoRecorder からメタデータを取得する実装
        # 現在は未実装のため、空のメタデータを返す
        return RecordingMetadataResponse()

    @router.post("/metadata", response_model=StandardResponse)
    async def update_recording_metadata(
        request: RecordingMetadataUpdateRequest,
    ) -> StandardResponse:
        """リアルタイム録画メタデータ更新。

        現在録画中のメタデータを手動で更新する。
        """
        try:
            # TODO: AutoRecorder にメタデータを保存する実装
            # 現在は未実装のため、成功を返す
            metadata_dict = {
                k: v for k, v in request.__dict__.items() if v is not None
            }
            server.logger.info("録画メタデータ更新", metadata=metadata_dict)
            return StandardResponse(success=True)
        except Exception as e:
            server.logger.error("録画メタデータ更新エラー", error=str(e))
            return StandardResponse(success=False, error=str(e))

    return router


def create_preview_router(server: WebAPIServer) -> APIRouter:
    """プレビュールーターを作成。

    Args:
        server: WebAPIServerインスタンス

    Returns:
        設定済みのAPIRouter
    """
    router = APIRouter(prefix="/api/preview", tags=["preview"])

    @router.get("/latest", response_model=PreviewFrameResponse)
    async def get_latest_preview_frame() -> PreviewFrameResponse:
        """最新のプレビューフレームを取得。"""
        # TODO: プレビュー機能未実装のため、常にフレームなしを返す
        return PreviewFrameResponse(
            has_frame=False, image_data_url=None, timestamp=None
        )

    return router


__all__ = ["create_recording_router", "create_preview_router"]
