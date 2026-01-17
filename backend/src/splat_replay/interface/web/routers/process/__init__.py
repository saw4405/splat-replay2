from fastapi import APIRouter, HTTPException, status

from splat_replay.interface.web.server import WebAPIServer


def create_process_router(server: WebAPIServer) -> APIRouter:
    router = APIRouter(prefix="/api/process", tags=["process"])

    @router.post("/start")
    async def start_auto_process() -> dict[str, str]:
        """自動処理を開始する。"""
        try:
            await server.auto_process_service.start_auto_process()
        except RuntimeError as e:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail=str(e)
            ) from e
        return {"status": "ok"}

    @router.post("/sleep/start")
    async def start_auto_sleep() -> dict[str, str]:
        """自動スリープを開始する。"""
        try:
            await server.auto_process_service.start_auto_sleep()
        except RuntimeError as e:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail=str(e)
            ) from e
        return {"status": "ok"}

    return router
