"""FastAPI application factory and route definitions."""

from __future__ import annotations

import contextlib
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import Response, JSONResponse
from splat_replay.application.services.system.desktop_maintenance import (
    DesktopMaintenance,
)
from splat_replay.interface.gui.desktop_control import (
    DesktopSignals,
    describe_tray_status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from splat_replay.interface.web.routers import (
    create_assets_router,
    create_events_router,
    create_file_serving_router,
    create_history_router,
    create_metadata_router,
    create_notifications_router,
    create_process_router,
    create_recording_router,
    create_remote_access_router,
    create_settings_router,
    create_setup_router,
)
from splat_replay.interface.web.server import WebAPIServer


FRONTEND_ENTRY_HEADERS: dict[str, str] = {
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "Pragma": "no-cache",
}


def _frontend_file_response(file_path: str | Path) -> FileResponse:
    path = Path(file_path)
    if path.name == "index.html":
        return FileResponse(path, headers=FRONTEND_ENTRY_HEADERS)
    return FileResponse(path)


def create_app(server: WebAPIServer, enable_lifespan: bool = True) -> FastAPI:
    """FastAPIアプリケーションを作成する。

    Args:
        server: WebAPIServerインスタンス
        enable_lifespan: lifespan イベントを有効化するか（テスト時は False）

    Returns:
        FastAPIアプリケーション
    """
    setup_service = server.setup_service
    system_check_service = server.system_check_service
    system_setup_service = server.system_setup_service
    error_handler = server.error_handler
    logger = server.logger
    device_checker = server.device_checker
    recording_preparation_service = server.recording_preparation_service
    upload_use_case = server.upload_use_case
    active_mutations = 0
    maintenance: DesktopMaintenance | None = None
    signals: DesktopSignals | None = None

    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        nonlocal maintenance, signals
        # Startup
        import asyncio

        signals = getattr(_app.state, "desktop_signals", None)
        auto_recording_use_case = server.auto_recording_use_case_factory()
        if signals is not None:
            maintenance = DesktopMaintenance(
                auto_recording_use_case,
                server.auto_process_service,
                signals.requested.is_set,
                signals.ready.set,
                lambda: active_mutations == 0
                and server.auto_recorder.get_state() == "STOPPED",
                quitting=signals.quitting.is_set,
            )
            auto_recording_use_case.maintenance_check = maintenance.check

        async def run_workers() -> None:
            if signals is not None:
                while not signals.activated.is_set():
                    await asyncio.sleep(0.1)
            await auto_recording_use_case.start_background()
            await server.auto_process_service.start()

        auto_process_task = asyncio.create_task(run_workers())

        async def check_stopped_worker() -> None:
            # 稼働中はフレーム境界が所有する。停止完了後だけここで判定する。
            while True:
                if signals is not None:
                    icon, text = describe_tray_status(
                        server.auto_recorder.get_state(),
                        server.start_edit_upload_uc.get_state(),
                        auto_recording_use_case.status(),
                        auto_recording_use_case.power_status().value,
                    )
                    signals.tray_status.value = f"{icon}|{text}".encode(
                        "utf-8"
                    )
                if (
                    maintenance is not None
                    and auto_recording_use_case.status() == "stopped"
                ):
                    maintenance.check()
                await asyncio.sleep(0.1)

        maintenance_task = (
            asyncio.create_task(check_stopped_worker())
            if signals is not None
            else None
        )
        if signals is not None:
            signals.started.set()
        try:
            yield
        finally:
            # Shutdown
            if maintenance_task is not None:
                maintenance_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await maintenance_task
            await auto_recording_use_case.stop_background()
            auto_process_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await auto_process_task
            auto_recording_use_case.maintenance_check = None

    # テスト時は lifespan を無効化
    if enable_lifespan:
        app = FastAPI(title="Splat Replay Web API", lifespan=lifespan)
    else:
        app = FastAPI(title="Splat Replay Web API")

    @app.middleware("http")
    async def guard_maintenance(
        request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        nonlocal active_mutations
        if request.method in {"GET", "HEAD", "OPTIONS"}:
            return await call_next(request)
        if (maintenance is not None and maintenance.entered) or (
            signals is not None and not signals.activated.is_set()
        ):
            return JSONResponse(
                {"detail": "更新準備中です。しばらくお待ちください。"},
                status_code=503,
            )
        active_mutations += 1
        try:
            return await call_next(request)
        finally:
            active_mutations -= 1

    # CORS設定 (開発時 & pywebview)
    # pywebview からのアクセスも許可するため、127.0.0.1:8000 と localhost:8000 を追加
    # type: ignore[arg-type] - FastAPIのadd_middlewareとStarletteのCORSMiddlewareの型定義の不一致
    app.add_middleware(
        CORSMiddleware,  # type: ignore[arg-type]
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:8000",
            "http://127.0.0.1:8000",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 静的ファイル配信 (フロントエンド)
    frontend_dist = server.project_root / "frontend" / "dist"
    frontend_exists = frontend_dist.is_dir()
    frontend_assets_dir = frontend_dist / "assets"

    if frontend_exists:
        # 静的ファイルをマウント (APIルート以外)
        if frontend_assets_dir.is_dir():
            app.mount(
                "/assets",
                StaticFiles(directory=str(frontend_assets_dir)),
                name="assets",
            )

    # ヘルスチェックエンドポイント (常に有効)
    @app.get("/api/health")
    async def health() -> dict[str, str]:
        """ヘルスチェックエンドポイント"""
        return {"status": "ok"}

    # セットアップルーターを登録
    setup_router = create_setup_router(
        setup_service=setup_service,
        system_check_service=system_check_service,
        system_setup_service=system_setup_service,
        error_handler=error_handler,
        logger=logger,
        device_checker=device_checker,
        recording_preparation_service=recording_preparation_service,
        auto_uploader=upload_use_case.uploader,
    )
    app.include_router(setup_router)

    # 各機能ルーターを登録
    events_router = create_events_router(server)
    app.include_router(events_router)

    recording_router = create_recording_router(server)
    app.include_router(recording_router)

    assets_router = create_assets_router(server)
    app.include_router(assets_router)

    # ファイル配信ルーター（静的リソース配信、/apiプレフィックス無し）
    file_serving_router = create_file_serving_router(server)
    app.include_router(file_serving_router)

    # 通知ルーターを登録
    notifications_router = create_notifications_router(server.assets_dir)
    app.include_router(notifications_router)

    metadata_router = create_metadata_router(server)
    app.include_router(metadata_router)

    settings_router = create_settings_router(server)
    app.include_router(settings_router)

    remote_access_router = create_remote_access_router(server)
    app.include_router(remote_access_router)

    process_router = create_process_router(server)
    app.include_router(process_router)

    history_router = create_history_router(server)
    app.include_router(history_router)

    # === SPA用 Catch-all ルート (最後に定義してAPIルートより優先度を下げる) ===
    if frontend_exists:

        @app.get("/{full_path:path}")
        async def serve_frontend(full_path: str) -> FileResponse:
            """SPAフロントエンド配信 (APIパス以外)"""
            # APIパスは既に上記で定義済みなので、ここには来ない
            # ただし念のため明示的に除外
            if full_path.startswith("api/"):
                raise HTTPException(
                    status_code=404, detail="API endpoint not found"
                )

            # セキュリティ: パストラバーサル・不正パス検出
            # 1. ..を含むパス
            # 2. 絶対パスの開始
            # 3. システムディレクトリの疑い（etc, usr, var, sys, proc等）
            suspicious_patterns = [
                "etc/",
                "usr/",
                "var/",
                "sys/",
                "proc/",
                "root/",
                "home/",
            ]
            if (
                ".." in full_path
                or full_path.startswith("/")
                or any(
                    full_path.startswith(pattern)
                    for pattern in suspicious_patterns
                )
            ):
                raise HTTPException(status_code=400, detail="Invalid path")

            # ファイルが存在する場合はそれを返す
            file_path = frontend_dist / full_path
            if file_path.is_file():
                return _frontend_file_response(file_path)

            # それ以外はindex.htmlを返す (SPAルーティング)
            return _frontend_file_response(frontend_dist / "index.html")

    return app


__all__ = ["create_app"]
__all__ = ["create_app"]
