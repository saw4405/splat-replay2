"""設定・デバイス管理ルーター。

責務：
- アプリケーション設定の取得・更新
- デバイス状態の取得
- 許可ダイアログの表示状態管理
"""

from __future__ import annotations

from typing import TYPE_CHECKING, List

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from splat_replay.application.services.common.settings_service import (
    SectionUpdate,
    SettingsServiceError,
    UnknownSettingsFieldError,
    UnknownSettingsSectionError,
)
from splat_replay.interface.web.schemas import SettingsUpdateRequest

if TYPE_CHECKING:
    from splat_replay.interface.web.server import WebAPIServer


def create_settings_router(server: WebAPIServer) -> APIRouter:
    """設定・デバイス管理ルーターを作成。

    Args:
        server: WebAPIServerインスタンス

    Returns:
        設定済みのAPIRouter
    """
    router = APIRouter(prefix="/api", tags=["settings"])

    # === 設定 ===

    @router.get("/settings")
    async def get_settings() -> JSONResponse:
        """アプリケーション設定を取得。"""
        sections = server.settings_service.fetch_sections()
        return JSONResponse(content={"sections": sections})

    @router.put("/settings")
    async def update_settings(
        request: SettingsUpdateRequest,
    ) -> JSONResponse:
        """アプリケーション設定を更新。"""
        updates: List[SectionUpdate] = [
            SectionUpdate(id=section.id, values=section.values)
            for section in request.sections
        ]
        try:
            server.settings_service.update_sections(updates)
            section_ids = {section.id for section in request.sections}
            if "obs" in section_ids:
                server.recording_preparation_service.reload_obs_settings()
            if "capture_device" in section_ids:
                server.device_checker.update_settings(
                    server.recording_preparation_service.get_capture_device_settings()
                )
        except UnknownSettingsSectionError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
            ) from exc
        except UnknownSettingsFieldError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
            ) from exc
        except ValidationError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=exc.errors(),
            ) from exc
        except SettingsServiceError as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(exc),
            ) from exc
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(exc),
            ) from exc

        return JSONResponse(content={"status": "ok"})

    # === デバイス ===

    @router.get("/device/status")
    async def get_device_status() -> JSONResponse:
        """デバイス状態を取得。"""
        try:
            is_connected = server.device_checker.is_connected()
            return JSONResponse(content=is_connected)
        except Exception as e:
            server.logger.error("Failed to get device status", error=str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to get device status",
            ) from e

    # === 許可ダイアログ ===

    @router.get("/settings/camera-permission-dialog")
    async def get_camera_permission_dialog_status() -> JSONResponse:
        """カメラ許可ダイアログの表示状態を取得。"""
        try:
            shown = server.setup_service.is_camera_permission_dialog_shown()
            return JSONResponse(content={"shown": shown})
        except Exception as e:
            server.logger.error(
                "Failed to get camera permission dialog status", error=str(e)
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to get camera permission dialog status",
            )

    @router.post("/settings/camera-permission-dialog")
    async def mark_camera_permission_dialog_shown(
        request: dict[str, bool],
    ) -> JSONResponse:
        """カメラ許可ダイアログを表示済みとしてマーク。"""
        try:
            if request.get("shown", False):
                server.setup_service.mark_camera_permission_dialog_shown()
            return JSONResponse(content={"status": "ok"})
        except Exception as e:
            server.logger.error(
                "Failed to mark camera permission dialog as shown",
                error=str(e),
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to mark camera permission dialog as shown",
            )

    @router.get("/settings/youtube-permission-dialog")
    async def get_youtube_permission_dialog_status() -> JSONResponse:
        """YouTube権限ダイアログの表示状態を取得。"""
        try:
            shown = server.setup_service.is_youtube_permission_dialog_shown()
            return JSONResponse(content={"shown": shown})
        except Exception as e:
            server.logger.error(
                "Failed to get youtube permission dialog status", error=str(e)
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to get youtube permission dialog status",
            )

    @router.post("/settings/youtube-permission-dialog")
    async def mark_youtube_permission_dialog_shown(
        request: dict[str, bool],
    ) -> JSONResponse:
        """YouTube権限ダイアログを表示済みとしてマーク。"""
        try:
            if request.get("shown", False):
                server.setup_service.mark_youtube_permission_dialog_shown()
            return JSONResponse(content={"status": "ok"})
        except Exception as e:
            server.logger.error(
                "Failed to mark youtube permission dialog as shown",
                error=str(e),
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to mark youtube permission dialog as shown",
            )

    return router


__all__ = ["create_settings_router"]
