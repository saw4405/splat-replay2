"""FastAPI アプリケーションの組み立て。"""

from __future__ import annotations

from typing import cast

import punq
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.responses import StreamingResponse
from structlog.stdlib import BoundLogger

from splat_replay.application.services import AutoRecorder, DeviceChecker
from splat_replay.infrastructure.runtime.runtime import AppRuntime
from splat_replay.shared.di import configure_container, resolve
from splat_replay.web.controllers import (
    AssetController,
    AutoRecorderAlreadyRunningError,
    AutoRecorderController,
    CommandExecutionError,
)
from splat_replay.web.models import (
    AssetEditedDirResponseModel,
    AutoRecorderStartResponseModel,
)
from splat_replay.web.preview import mjpeg_stream


def _build_container() -> punq.Container:
    """DI コンテナを初期化して返す。"""

    return configure_container()


_CONTAINER: punq.Container = _build_container()


def _get_container() -> punq.Container:
    """DI コンテナを依存解決用に返す。"""

    return _CONTAINER


def _get_runtime(container: punq.Container) -> AppRuntime:
    """AppRuntime を取得する。"""

    runtime = cast(AppRuntime, resolve(container, AppRuntime))
    return runtime


def _runtime_dependency() -> AppRuntime:
    """FastAPI 依存関係として AppRuntime を提供する。"""

    return _get_runtime(_get_container())


def _get_logger() -> BoundLogger:
    """アプリ共通ロガーを取得する。"""

    container = _get_container()
    return cast(BoundLogger, resolve(container, BoundLogger))


def _get_asset_controller() -> AssetController:
    """AssetController を生成する。"""

    runtime = _get_runtime(_get_container())
    return AssetController(runtime.command_bus)


def _get_auto_recorder_controller() -> AutoRecorderController:
    """AutoRecorderController を生成する。"""

    container = _get_container()
    runtime = _get_runtime(container)
    auto_recorder = cast(AutoRecorder, resolve(container, AutoRecorder))
    device_checker = cast(DeviceChecker, resolve(container, DeviceChecker))
    logger = _get_logger()
    return AutoRecorderController(
        runtime, auto_recorder, device_checker, logger
    )


def create_app() -> FastAPI:
    """FastAPI アプリケーションを構築する。"""

    app = FastAPI(title="Splat Replay API", version="0.1.0")

    @app.get(
        "/api/assets/edited/dir",
        response_model=AssetEditedDirResponseModel,
        tags=["assets"],
        summary="編集済み動画ディレクトリを取得",
        description=(
            "動画編集済みファイルを保存するディレクトリの絶対パスを返す。"
        ),
    )
    async def get_edited_dir(
        controller: AssetController = Depends(_get_asset_controller),
    ) -> AssetEditedDirResponseModel:
        try:
            path = await controller.get_edited_dir()
        except CommandExecutionError as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(exc),
            ) from exc
        return AssetEditedDirResponseModel(ok=True, path=path, error=None)

    @app.post(
        "/api/recorder/auto/start",
        response_model=AutoRecorderStartResponseModel,
        status_code=status.HTTP_202_ACCEPTED,
        tags=["recorder"],
        summary="自動録画を開始",
        description=(
            "キャプチャデバイスの接続を確認しつつ自動録画ループをバックグラウンドで起動する。"
        ),
    )
    async def start_auto_recorder(
        controller: AutoRecorderController = Depends(
            _get_auto_recorder_controller
        ),
    ) -> AutoRecorderStartResponseModel:
        try:
            waiting = controller.start_auto_recorder(wait_timeout=30.0)
        except AutoRecorderAlreadyRunningError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(exc),
            ) from exc
        except RuntimeError as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(exc),
            ) from exc

        message = (
            "キャプチャデバイスの接続を待機しています。接続され次第、録画を開始します。"
            if waiting
            else "自動録画を開始しました。"
        )
        return AutoRecorderStartResponseModel(
            ok=True,
            error=None,
            message=message,
            waiting_for_device=waiting,
        )

    @app.get(
        "/api/preview/stream",
        tags=["preview"],
        summary="ライブプレビューを取得",
        description="OBS から取得した最新フレームを MJPEG ストリームで返す。",
    )
    async def stream_preview(
        runtime: AppRuntime = Depends(_runtime_dependency),
        logger: BoundLogger = Depends(_get_logger),
    ) -> StreamingResponse:
        boundary = "frame"
        stream = mjpeg_stream(
            runtime.frame_hub, boundary=boundary, logger=logger
        )
        return StreamingResponse(
            stream,
            media_type=f"multipart/x-mixed-replace; boundary={boundary}",
            headers={"Cache-Control": "no-store"},
        )

    return app


app: FastAPI = create_app()

__all__ = ["app", "create_app"]
