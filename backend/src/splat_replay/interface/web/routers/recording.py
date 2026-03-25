"""録画制御ルーター。

責務：
- 録画準備（OBS起動・仮想カメラ有効化）
- 録画開始・一時停止・再開・停止
- 録画状態の取得
- リアルタイムメタデータの取得・保存
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Literal

import cv2
from fastapi import APIRouter
from fastapi.responses import Response
from starlette import status
from pydantic import BaseModel
from splat_replay.application.metadata import recording_metadata_to_dict
from splat_replay.domain.models import RecordingMetadata
from splat_replay.interface.web.schemas import (
    RecordingMetadataResponse,
    RecordingMetadataUpdateRequest,
)

if TYPE_CHECKING:
    from splat_replay.interface.web.server import WebAPIServer


# ========================================
# Response Schemas
# ========================================


class StandardResponse(BaseModel):
    """標準レスポンススキーマ。"""

    success: bool
    error: str | None = None
    state: str | None = None


class RecorderStateResponse(BaseModel):
    """録画状態レスポンススキーマ。"""

    state: str


class RecorderPreviewModeResponse(BaseModel):
    """プレビュー入力種別レスポンス。"""

    mode: Literal["live_capture", "video_file"]


def _build_recording_metadata_response(
    metadata: RecordingMetadata,
) -> RecordingMetadataResponse:
    return RecordingMetadataResponse.parse_obj(
        recording_metadata_to_dict(metadata)
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

    @router.post("/disable-auto", response_model=StandardResponse)
    async def disable_auto_recording() -> StandardResponse:
        """自動録画モードを停止する。"""
        try:
            use_case = server.auto_recording_use_case_factory()
            use_case.force_stop()
            for _ in range(100):
                if use_case.status() != "running":
                    break
                await asyncio.sleep(0.1)
            return StandardResponse(success=True, state=use_case.status())
        except Exception as e:
            error_handler.handle_error(
                e, context="自動録画停止", log_level="warning"
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

    @router.get("/preview-frame")
    async def get_preview_frame() -> Response:
        """最新フレームの JPEG プレビューを取得。"""
        frame = server.frame_source.get_latest()
        if frame is None:
            return Response(status_code=status.HTTP_204_NO_CONTENT)

        success, encoded = cv2.imencode(
            ".jpg",
            frame,
            [int(cv2.IMWRITE_JPEG_QUALITY), 80],
        )
        if not success:
            server.logger.warning("プレビューフレームの JPEG 化に失敗しました")
            return Response(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response(
            content=encoded.tobytes(),
            media_type="image/jpeg",
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                "Pragma": "no-cache",
                "Expires": "0",
            },
        )

    @router.get("/preview-mode", response_model=RecorderPreviewModeResponse)
    async def get_preview_mode() -> RecorderPreviewModeResponse:
        """プレビュー入力種別を取得。"""
        mode = server.preview_mode_resolver()
        return RecorderPreviewModeResponse(mode=mode)

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
            updates = request.dict(exclude_unset=True)
            use_case = server.auto_recording_use_case_factory()
            await use_case.update_metadata(updates)
            server.logger.info("録画メタデータ更新", metadata=updates)
            return StandardResponse(success=True)
        except Exception as e:
            error_handler.handle_error(e, context="録画メタデータ更新")

    return router


__all__ = ["create_recording_router"]
