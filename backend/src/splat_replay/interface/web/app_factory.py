"""FastAPI application factory and route definitions."""

from __future__ import annotations

import contextlib

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from splat_replay.interface.web.routers import (
    create_assets_router,
    create_events_router,
    create_metadata_router,
    create_notifications_router,
    create_process_router,
    create_recording_router,
    create_settings_router,
    create_setup_router,
)
from splat_replay.interface.web.server import WebAPIServer


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

    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        # Startup
        import asyncio

        auto_process_task = asyncio.create_task(
            server.auto_process_service.start()
        )
        yield
        # Shutdown
        auto_process_task.cancel()
        with contextlib.suppress(Exception):
            await auto_process_task

    # テスト時は lifespan を無効化
    if enable_lifespan:
        app = FastAPI(title="Splat Replay Web API", lifespan=lifespan)
    else:
        app = FastAPI(title="Splat Replay Web API")

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
    frontend_exists = frontend_dist.exists()

    if frontend_exists:
        # 静的ファイルをマウント (APIルート以外)
        app.mount(
            "/assets",
            StaticFiles(directory=str(frontend_dist / "assets")),
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

    # 通知ルーターを登録
    notifications_router = create_notifications_router(server.assets_dir)
    app.include_router(notifications_router)

    metadata_router = create_metadata_router(server)
    app.include_router(metadata_router)

    settings_router = create_settings_router(server)
    app.include_router(settings_router)

    process_router = create_process_router(server)
    app.include_router(process_router)

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

            # ファイルが存在する場合はそれを返す
            file_path = frontend_dist / full_path
            if file_path.is_file():
                return FileResponse(file_path)

            # それ以外はindex.htmlを返す (SPAルーティング)
            return FileResponse(frontend_dist / "index.html")

    return app


__all__ = ["create_app"]
__all__ = ["create_app"]
