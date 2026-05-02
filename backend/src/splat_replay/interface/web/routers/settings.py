"""Settings and device-related web routes."""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, AsyncGenerator, List

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
    AudioCalibrateRequest,
    CaptureDeviceDescriptorResponse,
    CaptureDeviceDiagnosticsResponse,
    CaptureDeviceRecoveryRequest,
    CaptureDeviceRecoveryResponse,
    SettingsUpdateRequest,
    SpeechTestRequest,
)
from starlette.responses import StreamingResponse

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

    @router.post("/settings/audio/calibrate")
    async def calibrate_audio(
        request: AudioCalibrateRequest,
    ) -> JSONResponse:
        import audioop
        import time

        import speech_recognition as sr

        mic_device_name = request.mic_device_name
        server.logger.info(
            "Audio calibration started",
            mic_device_name=mic_device_name,
        )

        def _calibrate() -> int:
            microphone_index = server.device_checker.find_microphone_index(
                mic_device_name
            )

            if microphone_index is None:
                raise ValueError("マイクが見つかりません")

            rms_values: list[int] = []
            with sr.Microphone(device_index=microphone_index) as source:
                # Realtek 等のドライバは AGC（自動ゲイン調整）を内蔵
                # しており、マイクを開いた直後は高ゲイン → 数秒で安定化
                # する。実際の SpeechTranscriber もマイクを開き続けるため、
                # AGC 安定後の値が実運用に合った閾値になる。
                # 5 秒のウォームアップで AGC を安定させてから測定する。
                warmup_end = time.monotonic() + 5.0
                while time.monotonic() < warmup_end:
                    source.stream.read(source.CHUNK)  # type: ignore[attr-defined]

                measure_end = time.monotonic() + 3.0
                while time.monotonic() < measure_end:
                    buffer = source.stream.read(source.CHUNK)  # type: ignore[attr-defined]
                    rms_values.append(audioop.rms(buffer, source.SAMPLE_WIDTH))  # type: ignore[attr-defined]

            if not rms_values:
                raise ValueError("音声サンプルを取得できませんでした")

            rms_values.sort()
            count = len(rms_values)
            # Q1（25 パーセンタイル）を環境音フロアの推定値とする。
            # Q1 は最も静かな 25% の代表値であり、測定中に偶発的な
            # 音声や衝撃音が混入しても影響を受けにくい。
            # p95 等の上位パーセンタイルは測定中のわずかな音で
            # 数十倍に跳ね上がり、再現性がない。
            #
            # listen() は energy > energy_threshold で発話開始を判定する。
            # dynamic_energy_threshold=False（固定閾値）の場合、閾値は
            # ノイズのピークを確実に超える必要がある。
            # Q1 × 10 は環境音の最大値の約 3〜5 倍に相当し、
            # 音声処理で信頼性のある検出に必要とされる約 20 dB の
            # SNR（信号対雑音比）を確保する。
            q1 = rms_values[count // 4]
            threshold = max(100, q1 * 10)

            server.logger.info(
                "Audio calibration result",
                sample_count=count,
                min_rms=rms_values[0],
                q1_rms=q1,
                max_rms=rms_values[-1],
                threshold=threshold,
            )

            return threshold

        try:
            threshold = await asyncio.wait_for(
                asyncio.to_thread(_calibrate), timeout=15.0
            )
            return JSONResponse(content={"energy_threshold": threshold})
        except asyncio.TimeoutError as exc:
            server.logger.error("Audio calibration timed out")
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="マイクの読み込みがタイムアウトしました。マイクが他の処理でブロックされている可能性があります。",
            ) from exc
        except Exception as exc:
            server.logger.error("Failed to calibrate audio", error=str(exc))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(exc),
            ) from exc

    @router.post("/settings/speech/test")
    async def test_speech_recognition(
        request: SpeechTestRequest,
    ) -> StreamingResponse:
        """音声認識テスト。マイクから録音してリアルタイムに認識結果をストリーム配信する。"""
        if server.speech_test_fn is None:
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail="音声認識テスト機能は利用できません。",
            ) from None

        server.logger.info(
            "音声認識テストを開始します",
            mic_device_name=request.mic_device_name,
        )

        speech_test = server.speech_test_fn

        async def event_stream() -> AsyncGenerator[str, None]:
            gen = speech_test(
                request.mic_device_name,
                overrides=request.overrides,
            )
            try:
                async for event in gen:
                    yield json.dumps(event, ensure_ascii=False) + "\n"
            except ValueError as exc:
                yield (
                    json.dumps(
                        {"type": "error", "detail": str(exc)},
                        ensure_ascii=False,
                    )
                    + "\n"
                )
            except Exception as exc:
                server.logger.error(
                    "音声認識テストに失敗しました", error=str(exc)
                )
                yield (
                    json.dumps(
                        {"type": "error", "detail": str(exc)},
                        ensure_ascii=False,
                    )
                    + "\n"
                )
            finally:
                await gen.aclose()

        return StreamingResponse(
            event_stream(),
            media_type="application/x-ndjson",
        )

    return router


__all__ = ["create_settings_router"]
