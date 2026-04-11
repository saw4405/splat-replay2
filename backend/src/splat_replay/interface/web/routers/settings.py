"""Settings and device-related web routes."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, List

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from splat_replay.application.interfaces import (
    CaptureDeviceDescriptor,
    CaptureDeviceRecoveryResult,
)
from splat_replay.application.services.common.settings_service import (
    SectionUpdate,
    SettingsServiceError,
    UnknownSettingsFieldError,
    UnknownSettingsSectionError,
)
from splat_replay.interface.web.schemas import (
    CaptureDeviceDiagnosticsResponse,
    CaptureDeviceDescriptorResponse,
    CaptureDeviceRecoveryRequest,
    CaptureDeviceRecoveryResponse,
    SettingsUpdateRequest,
)

if TYPE_CHECKING:
    from splat_replay.interface.web.server import WebAPIServer


def _to_capture_device_descriptor_response(
    descriptor: CaptureDeviceDescriptor,
) -> CaptureDeviceDescriptorResponse:
    return CaptureDeviceDescriptorResponse(
        name=descriptor.name,
        alternative_name=descriptor.alternative_name,
        pnp_instance_id=descriptor.pnp_instance_id,
        hardware_id=descriptor.hardware_id,
        location_path=descriptor.location_path,
        parent_instance_id=descriptor.parent_instance_id,
    )


def _to_capture_device_recovery_response(
    recovery: CaptureDeviceRecoveryResult,
) -> CaptureDeviceRecoveryResponse:
    return CaptureDeviceRecoveryResponse(
        attempted=recovery.attempted,
        recovered=recovery.recovered,
        message=recovery.message,
        action=recovery.action,
    )


def create_settings_router(server: WebAPIServer) -> APIRouter:
    """Create the settings router."""
    router = APIRouter(prefix="/api", tags=["settings"])

    @router.get("/settings")
    async def get_settings() -> JSONResponse:
        sections = server.settings_service.fetch_sections()
        return JSONResponse(content={"sections": sections})

    @router.get("/settings/webview-render-mode")
    async def get_webview_render_mode() -> JSONResponse:
        render_mode = server.settings_service.fetch_webview_render_mode()
        return JSONResponse(content={"render_mode": render_mode})

    @router.put("/settings")
    async def update_settings(
        request: SettingsUpdateRequest,
    ) -> JSONResponse:
        current_capture_device_name = server.recording_preparation_service.get_capture_device_settings().name
        requested_capture_device_name = next(
            (
                section.values.get("name")
                for section in request.sections
                if section.id == "capture_device"
                and isinstance(section.values.get("name"), str)
            ),
            None,
        )
        updates: List[SectionUpdate] = [
            SectionUpdate(id=section.id, values=section.values)
            for section in request.sections
        ]
        try:
            server.settings_service.update_sections(updates)
            section_ids = {section.id for section in request.sections}
            if "obs" in section_ids:
                server.recording_preparation_service.reload_obs_settings()
            if (
                requested_capture_device_name is not None
                and requested_capture_device_name
                != current_capture_device_name
            ):
                server.device_checker.rebind_configured_device()
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
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
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

    @router.get("/device/status")
    async def get_device_status() -> JSONResponse:
        try:
            connected = await asyncio.to_thread(
                server.device_checker.is_connected
            )
            return JSONResponse(content=connected)
        except Exception as exc:
            server.logger.error("Failed to get device status", error=str(exc))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to get device status",
            ) from exc

    @router.post(
        "/device/recover", response_model=CaptureDeviceRecoveryResponse
    )
    async def recover_device(
        request: CaptureDeviceRecoveryRequest,
    ) -> CaptureDeviceRecoveryResponse:
        try:
            result = await asyncio.to_thread(
                server.device_checker.recover_device, request.trigger
            )
            return _to_capture_device_recovery_response(result)
        except Exception as exc:
            server.logger.error("Failed to recover device", error=str(exc))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to recover device",
            ) from exc

    @router.get(
        "/device/diagnostics",
        response_model=CaptureDeviceDiagnosticsResponse,
    )
    async def get_device_diagnostics() -> CaptureDeviceDiagnosticsResponse:
        try:
            diagnostics = await asyncio.to_thread(
                server.device_checker.get_diagnostics
            )
            return CaptureDeviceDiagnosticsResponse(
                configured_device_name=diagnostics.configured_device_name,
                configured_hardware_id=diagnostics.configured_hardware_id,
                configured_location_path=diagnostics.configured_location_path,
                configured_parent_instance_id=diagnostics.configured_parent_instance_id,
                resolved_device=(
                    _to_capture_device_descriptor_response(
                        diagnostics.resolved_device
                    )
                    if diagnostics.resolved_device is not None
                    else None
                ),
                available_devices=[
                    _to_capture_device_descriptor_response(descriptor)
                    for descriptor in diagnostics.available_devices
                ],
                last_recovery=(
                    _to_capture_device_recovery_response(
                        diagnostics.last_recovery
                    )
                    if diagnostics.last_recovery is not None
                    else None
                ),
            )
        except Exception as exc:
            server.logger.error(
                "Failed to get device diagnostics", error=str(exc)
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to get device diagnostics",
            ) from exc

    @router.get("/settings/camera-permission-dialog")
    async def get_camera_permission_dialog_status() -> JSONResponse:
        try:
            shown = server.setup_service.is_camera_permission_dialog_shown()
            return JSONResponse(content={"shown": shown})
        except Exception as exc:
            server.logger.error(
                "Failed to get camera permission dialog status",
                error=str(exc),
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to get camera permission dialog status",
            ) from exc

    @router.post("/settings/camera-permission-dialog")
    async def mark_camera_permission_dialog_shown(
        request: dict[str, bool],
    ) -> JSONResponse:
        try:
            if request.get("shown", False):
                server.setup_service.mark_camera_permission_dialog_shown()
            return JSONResponse(content={"status": "ok"})
        except Exception as exc:
            server.logger.error(
                "Failed to mark camera permission dialog as shown",
                error=str(exc),
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to mark camera permission dialog as shown",
            ) from exc

    @router.get("/settings/youtube-permission-dialog")
    async def get_youtube_permission_dialog_status() -> JSONResponse:
        try:
            shown = server.setup_service.is_youtube_permission_dialog_shown()
            return JSONResponse(content={"shown": shown})
        except Exception as exc:
            server.logger.error(
                "Failed to get youtube permission dialog status",
                error=str(exc),
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to get youtube permission dialog status",
            ) from exc

    @router.post("/settings/youtube-permission-dialog")
    async def mark_youtube_permission_dialog_shown(
        request: dict[str, bool],
    ) -> JSONResponse:
        try:
            if request.get("shown", False):
                server.setup_service.mark_youtube_permission_dialog_shown()
            return JSONResponse(content={"status": "ok"})
        except Exception as exc:
            server.logger.error(
                "Failed to mark youtube permission dialog as shown",
                error=str(exc),
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to mark youtube permission dialog as shown",
            ) from exc

    return router


__all__ = ["create_settings_router"]
