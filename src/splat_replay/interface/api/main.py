"""FastAPI を用いたバックエンドエントリーポイント。"""

from __future__ import annotations

import asyncio
from concurrent.futures import Future as ThreadFuture
import threading
from pathlib import Path
from typing import Any, Coroutine, List

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from splat_replay.application.services import (
    AutoEditor,
    AutoRecorder,
    AutoUploader,
    DeviceChecker,
)
from splat_replay.application.services.queries import AssetQueryService
from splat_replay.application.use_cases import AutoUseCase
from splat_replay.domain.models import VideoAsset
from splat_replay.domain.services import StateMachine
from splat_replay.infrastructure.runtime.events import Event
from splat_replay.infrastructure.runtime.runtime import AppRuntime
from splat_replay.shared.config import AppSettings, BehaviorSettings
from splat_replay.shared.di import configure_container, resolve
from splat_replay.shared.logger import get_logger

from .event_log import EventLog
from .schemas import (
    AssetMetadataUpdate,
    BehaviorSettingsResponse,
    BehaviorSettingsUpdate,
    EditedAssetResponse,
    EventResponse,
    OperationResponse,
    RecorderAction,
    RecorderStateResponse,
    VideoAssetResponse,
)
from .utils import decode_path, encode_path, normalize_payload

app = FastAPI(title="Splat Replay API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

_container = configure_container()
_logger = get_logger()
_runtime = resolve(_container, AppRuntime)
_state_machine = resolve(_container, StateMachine)
_auto_recorder = resolve(_container, AutoRecorder)
_auto_editor = resolve(_container, AutoEditor)
_auto_uploader = resolve(_container, AutoUploader)
_asset_query = resolve(_container, AssetQueryService)
_device_checker = resolve(_container, DeviceChecker)
_settings = resolve(_container, AppSettings)
_behavior_settings = resolve(_container, BehaviorSettings)
_event_log = EventLog(_runtime.event_bus)

_auto_recorder_lock = threading.Lock()
_auto_recorder_future: ThreadFuture[None] | None = None


@app.get("/health")
def health() -> dict[str, str]:
    """疎通確認用エンドポイント。"""

    return {"status": "ok"}


@app.get("/recorder/state", response_model=RecorderStateResponse)
def recorder_state() -> RecorderStateResponse:
    """録画状態および監視タスク状態を返す。"""

    return RecorderStateResponse(
        state=_state_machine.state.value,
        loop_running=_is_auto_recorder_running(),
    )


@app.post("/recorder/{action}", response_model=OperationResponse)
async def recorder_control(action: RecorderAction) -> OperationResponse:
    """録画制御コマンドを実行する。"""

    command = f"recorder.{action.value}"
    await _submit_command(command)
    return OperationResponse(status="accepted")


@app.post("/recorder/monitor/start", response_model=OperationResponse)
def start_auto_recorder_monitor() -> OperationResponse:
    """自動録画監視タスクを開始する。"""

    try:
        started = _start_auto_recorder_loop()
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover - 想定外の失敗
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if not started:
        return OperationResponse(
            status="already_running", message="自動録画監視は既に動作中です"
        )
    return OperationResponse(status="accepted")


@app.post("/recorder/monitor/stop", response_model=OperationResponse)
def stop_auto_recorder_monitor() -> OperationResponse:
    """自動録画監視タスクを停止する。"""

    running = _stop_auto_recorder_loop()
    if not running:
        return OperationResponse(
            status="stopped", message="監視タスクは停止済みです"
        )
    return OperationResponse(status="accepted")


@app.post("/workflow/auto", response_model=OperationResponse)
def run_auto_workflow() -> OperationResponse:
    """録画からアップロードまで一括実行する。"""

    use_case = resolve(_container, AutoUseCase)
    _schedule_runtime_task(use_case.execute())
    return OperationResponse(status="accepted")


@app.post("/workflow/edit", response_model=OperationResponse)
def run_auto_edit() -> OperationResponse:
    """自動編集をバックグラウンドで開始する。"""

    _schedule_runtime_task(_auto_editor.execute())
    return OperationResponse(status="accepted")


@app.post("/workflow/edit/cancel", response_model=OperationResponse)
def cancel_auto_edit() -> OperationResponse:
    """実行中の自動編集をキャンセルする。"""

    _auto_editor.request_cancel()
    return OperationResponse(status="accepted")


@app.post("/workflow/upload", response_model=OperationResponse)
def run_auto_upload() -> OperationResponse:
    """編集済み動画の自動アップロードを開始する。"""

    _schedule_runtime_task(_auto_uploader.execute())
    return OperationResponse(status="accepted")


@app.post("/workflow/upload/cancel", response_model=OperationResponse)
def cancel_auto_upload() -> OperationResponse:
    """自動アップロードをキャンセルする。"""

    _auto_uploader.request_cancel()
    return OperationResponse(status="accepted")


@app.get("/assets/recorded", response_model=List[VideoAssetResponse])
async def list_recorded_assets() -> List[VideoAssetResponse]:
    """録画済み動画の一覧を取得する。"""

    assets = await _asset_query.list_with_length()
    return [
        _to_video_asset_response(asset, length) for asset, length in assets
    ]


@app.put(
    "/assets/recorded/{asset_id}/metadata", response_model=OperationResponse
)
async def update_recorded_metadata(
    asset_id: str, payload: AssetMetadataUpdate
) -> OperationResponse:
    """録画済み動画のメタデータを更新する。"""

    path = _decode_asset_id(asset_id)
    success = await _asset_query.save_metadata(path, payload.metadata)
    if not success:
        raise HTTPException(
            status_code=400, detail="メタデータの保存に失敗しました"
        )
    return OperationResponse(status="accepted")


@app.delete("/assets/recorded/{asset_id}", response_model=OperationResponse)
async def delete_recorded(asset_id: str) -> OperationResponse:
    """録画済み動画を削除する。"""

    path = _decode_asset_id(asset_id)
    success = await _asset_query.delete(path)
    if not success:
        raise HTTPException(
            status_code=404, detail="対象の動画が見つかりません"
        )
    return OperationResponse(status="accepted")


@app.get("/assets/edited", response_model=List[EditedAssetResponse])
async def list_edited_assets() -> List[EditedAssetResponse]:
    """編集済み動画の一覧を取得する。"""

    items = await _asset_query.list_edited_with_length()
    responses: list[EditedAssetResponse] = []
    for path, length, metadata in items:
        responses.append(
            EditedAssetResponse(
                asset_id=encode_path(path),
                video_path=str(path),
                length_seconds=length,
                metadata=metadata,
            )
        )
    return responses


@app.delete("/assets/edited/{asset_id}", response_model=OperationResponse)
async def delete_edited(asset_id: str) -> OperationResponse:
    """編集済み動画を削除する。"""

    path = _decode_asset_id(asset_id)
    success = await _asset_query.delete_edited(path)
    if not success:
        raise HTTPException(
            status_code=404, detail="対象の動画が見つかりません"
        )
    return OperationResponse(status="accepted")


@app.get("/events", response_model=List[EventResponse])
def list_events(
    after: float | None = Query(None, description="取得済みタイムスタンプ"),
) -> List[EventResponse]:
    """イベントログを取得する。"""

    events = _event_log.list(after_ts=after)
    return [_to_event_response(ev) for ev in events]


@app.get("/settings/behavior", response_model=BehaviorSettingsResponse)
def get_behavior_settings() -> BehaviorSettingsResponse:
    """挙動設定を取得する。"""

    return BehaviorSettingsResponse(
        edit_after_power_off=_behavior_settings.edit_after_power_off,
        sleep_after_upload=_behavior_settings.sleep_after_upload,
    )


@app.put("/settings/behavior", response_model=BehaviorSettingsResponse)
def update_behavior_settings(
    payload: BehaviorSettingsUpdate,
) -> BehaviorSettingsResponse:
    """挙動設定を更新し、設定ファイルへ保存する。"""

    _behavior_settings.edit_after_power_off = payload.edit_after_power_off
    _behavior_settings.sleep_after_upload = payload.sleep_after_upload
    _settings.behavior = _behavior_settings
    _settings.save_to_toml()
    return BehaviorSettingsResponse(
        edit_after_power_off=_behavior_settings.edit_after_power_off,
        sleep_after_upload=_behavior_settings.sleep_after_upload,
    )


@app.on_event("shutdown")
def shutdown() -> None:
    """アプリ終了時のクリーンアップ。"""

    _event_log.close()
    _runtime.stop()


async def _submit_command(name: str) -> None:
    result = await asyncio.wrap_future(_runtime.command_bus.submit(name))
    if not result.ok:
        detail = (
            str(result.error) if result.error else "コマンド実行に失敗しました"
        )
        raise HTTPException(status_code=400, detail=detail)


def _schedule_runtime_task(
    coro: Coroutine[Any, Any, Any],
) -> ThreadFuture[Any]:
    loop = _runtime.loop
    if loop is None or not loop.is_running():
        raise HTTPException(
            status_code=500, detail="アプリケーションループが起動していません"
        )
    return asyncio.run_coroutine_threadsafe(coro, loop)


def _start_auto_recorder_loop() -> bool:
    global _auto_recorder_future
    with _auto_recorder_lock:
        if _auto_recorder_future and not _auto_recorder_future.done():
            return False
        loop = _runtime.loop
        if loop is None or not loop.is_running():
            raise HTTPException(
                status_code=500,
                detail="アプリケーションループが起動していません",
            )

        future = asyncio.run_coroutine_threadsafe(
            _auto_recorder_worker(), loop
        )
        _auto_recorder_future = future

    future.add_done_callback(_auto_recorder_done_callback)
    return True


def _stop_auto_recorder_loop() -> bool:
    with _auto_recorder_lock:
        future = _auto_recorder_future
    if future is None or future.done():
        return False
    _auto_recorder.force_stop_loop()
    return True


def _is_auto_recorder_running() -> bool:
    with _auto_recorder_lock:
        future = _auto_recorder_future
    return future is not None and not future.done()


def _auto_recorder_done_callback(_: ThreadFuture[None]) -> None:
    global _auto_recorder_future
    with _auto_recorder_lock:
        _auto_recorder_future = None


async def _auto_recorder_worker() -> None:
    try:
        connected = await _device_checker.wait_for_device_connection()
        if not connected:
            _logger.error("キャプチャデバイスが見つかりません")
            return
        await _auto_recorder.execute()
    except Exception as exc:  # noqa: BLE001
        _logger.error("自動録画監視タスクで例外が発生", error=str(exc))


def _to_video_asset_response(
    asset: VideoAsset, length: float | None
) -> VideoAssetResponse:
    metadata = asset.metadata.to_dict() if asset.metadata else None
    return VideoAssetResponse(
        asset_id=encode_path(asset.video),
        video_path=str(asset.video),
        subtitle_path=str(asset.subtitle) if asset.subtitle else None,
        thumbnail_path=str(asset.thumbnail) if asset.thumbnail else None,
        length_seconds=length,
        metadata=metadata,
    )


def _decode_asset_id(asset_id: str) -> Path:
    try:
        return decode_path(asset_id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=400, detail="不正な asset_id です"
        ) from exc


def _to_event_response(ev: Event) -> EventResponse:
    payload = {k: normalize_payload(v) for k, v in ev.payload.items()}
    return EventResponse(
        id=str(ev.id),
        type=ev.type,
        timestamp=ev.ts,
        severity=ev.severity,
        payload=payload,
        correlation_id=str(ev.correlation_id) if ev.correlation_id else None,
    )
