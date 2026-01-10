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
from splat_replay.domain.models import (
    BattleResult,
    RecordingMetadata,
    SalmonResult,
)

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


class RecordingMetadataResponse(BaseModel):
    """録画メタデータレスポンススキーマ。"""

    game_mode: str | None = Field(None, description="ゲームモード")
    stage: str | None = Field(None, description="ステージ")
    started_at: str | None = Field(None, description="開始時刻")
    match: str | None = Field(None, description="マッチ")
    rule: str | None = Field(None, description="ルール")
    rate: str | None = Field(None, description="レート")
    judgement: str | None = Field(None, description="判定")
    kill: int | None = Field(None, description="キル数")
    death: int | None = Field(None, description="デス数")
    special: int | None = Field(None, description="スペシャル数")
    hazard: int | None = Field(None, description="危険度")
    golden_egg: int | None = Field(None, description="金イクラ数")
    power_egg: int | None = Field(None, description="イクラ数")
    rescue: int | None = Field(None, description="救助数")
    rescued: int | None = Field(None, description="救助された数")


class RecordingMetadataUpdateRequest(BaseModel):
    """録画メタデータ更新リクエストスキーマ。"""

    game_mode: str | None = None
    started_at: str | None = None
    match: str | None = None
    rule: str | None = None
    stage: str | None = None
    rate: str | None = None
    judgement: str | None = None
    kill: int | None = None
    death: int | None = None
    special: int | None = None
    hazard: int | None = None
    golden_egg: int | None = None
    power_egg: int | None = None
    rescue: int | None = None
    rescued: int | None = None


def _build_recording_metadata_response(
    metadata: RecordingMetadata,
) -> RecordingMetadataResponse:
    stage: str | None = None
    match: str | None = None
    rule: str | None = None
    kill: int | None = None
    death: int | None = None
    special: int | None = None
    hazard: int | None = None
    golden_egg: int | None = None
    power_egg: int | None = None
    rescue: int | None = None
    rescued: int | None = None

    result = metadata.result
    if isinstance(result, BattleResult):
        match = result.match.name
        rule = result.rule.name
        stage = result.stage.name
        kill = result.kill
        death = result.death
        special = result.special
    elif isinstance(result, SalmonResult):
        stage = result.stage.name
        hazard = result.hazard
        golden_egg = result.golden_egg
        power_egg = result.power_egg
        rescue = result.rescue
        rescued = result.rescued

    return RecordingMetadataResponse(
        game_mode=metadata.game_mode.name if metadata.game_mode else None,
        stage=stage,
        started_at=metadata.started_at.isoformat()
        if metadata.started_at
        else None,
        match=match,
        rule=rule,
        rate=str(metadata.rate) if metadata.rate else None,
        judgement=metadata.judgement.name if metadata.judgement else None,
        kill=kill,
        death=death,
        special=special,
        hazard=hazard,
        golden_egg=golden_egg,
        power_egg=power_egg,
        rescue=rescue,
        rescued=rescued,
    )


def create_recording_router(server: WebAPIServer) -> APIRouter:
    """録画制御ルーターを作成。

    Args:
        server: WebAPIServerインスタンス

    Returns:
        設定済みのAPIRouter
    """
    router = APIRouter(prefix="/api/recorder", tags=["recording"])
    error_handler = server.web_error_handler

    @router.post("/prepare", response_model=StandardResponse)
    async def prepare_recording() -> StandardResponse:
        """録画準備（OBS起動・仮想カメラ有効化）。"""
        try:
            await server.recording_preparation_service.prepare_recording()
            return StandardResponse(success=True)
        except Exception as e:
            error_handler.handle_error(
                e, context="録画準備", log_level="warning"
            )

    @router.post("/enable-auto", response_model=StandardResponse)
    async def enable_auto_recording() -> StandardResponse:
        """自動録画モードを有効化（バトル開始検知開始）。"""
        try:
            use_case = server.auto_recording_use_case_factory()
            started = await use_case.start_background()
            if not started:
                return StandardResponse(
                    success=True,
                    state=use_case.status(),
                )
            return StandardResponse(success=True, state=use_case.status())
        except Exception as e:
            error_handler.handle_error(
                e, context="自動録画有効化", log_level="warning"
            )

    @router.post("/start", response_model=StandardResponse)
    async def manual_start_recorder() -> StandardResponse:
        """手動録画開始。"""
        try:
            await server.auto_recorder.start()
            return StandardResponse(success=True)
        except Exception as e:
            error_handler.handle_error(
                e, context="手動録画開始", log_level="warning"
            )

    @router.post("/pause", response_model=StandardResponse)
    async def manual_pause_recorder() -> StandardResponse:
        """手動録画一時停止。"""
        try:
            await server.auto_recorder.pause()
            return StandardResponse(success=True)
        except Exception as e:
            error_handler.handle_error(
                e, context="手動録画一時停止", log_level="warning"
            )

    @router.post("/resume", response_model=StandardResponse)
    async def manual_resume_recorder() -> StandardResponse:
        """手動録画再開。"""
        try:
            await server.auto_recorder.resume()
            return StandardResponse(success=True)
        except Exception as e:
            error_handler.handle_error(
                e, context="手動録画再開", log_level="warning"
            )

    @router.post("/stop", response_model=StandardResponse)
    async def manual_stop_recorder() -> StandardResponse:
        """手動録画停止。"""
        try:
            await server.auto_recorder.stop()
            return StandardResponse(success=True)
        except Exception as e:
            error_handler.handle_error(
                e, context="手動録画停止", log_level="warning"
            )

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
        use_case = server.auto_recording_use_case_factory()
        metadata = await use_case.get_metadata()
        return _build_recording_metadata_response(metadata)

    @router.patch("/metadata", response_model=StandardResponse)
    async def update_recording_metadata(
        request: RecordingMetadataUpdateRequest,
    ) -> StandardResponse:
        """リアルタイム録画メタデータ更新。

        現在録画中のメタデータを手動で更新する。
        """
        try:
            updates = request.dict(exclude_none=True)
            use_case = server.auto_recording_use_case_factory()
            await use_case.update_metadata(updates)
            server.logger.info("録画メタデータ更新", metadata=updates)
            return StandardResponse(success=True)
        except Exception as e:
            error_handler.handle_error(e, context="録画メタデータ更新")

    return router


__all__ = ["create_recording_router"]
