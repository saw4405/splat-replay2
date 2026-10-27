"""サムネイルデザインと素材管理のAPI。"""

import asyncio
import base64
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response, FileResponse, JSONResponse
from pydantic import BaseModel

from splat_replay.application.services.editing.thumbnail_design_service import (
    ThumbnailDesignService,
)
from splat_replay.domain.config.video_edit import (
    ThumbnailDesign,
    THUMBNAIL_VARIABLES,
)


class PreviewRequest(BaseModel):
    design: ThumbnailDesign
    scenario: Literal["x", "event", "regular", "anarchy", "single"] = "x"
    include_layout: bool = False


class DeleteRequest(BaseModel):
    asset_id: str
    draft: ThumbnailDesign


def create_thumbnail_design_router(
    service: ThumbnailDesignService,
) -> APIRouter:
    router = APIRouter(
        prefix="/api/thumbnail-design", tags=["thumbnail-design"]
    )

    @router.get("")
    async def catalog() -> dict[str, object]:
        return {
            "assets": await asyncio.to_thread(service.catalog),
            "default_design": service.default_design().dict(),
            "variables": THUMBNAIL_VARIABLES,
        }

    @router.post("/preview")
    async def preview(request: PreviewRequest) -> Response:
        try:
            if request.include_layout:
                content, layout = await asyncio.to_thread(
                    service.preview_with_layout,
                    request.design,
                    request.scenario,
                )
                return JSONResponse(
                    {
                        "image": "data:image/png;base64,"
                        + base64.b64encode(content).decode("ascii"),
                        "layout": layout,
                    },
                    headers={"Cache-Control": "no-store"},
                )
            content = await asyncio.to_thread(
                service.preview, request.design, request.scenario
            )
            return Response(
                content,
                media_type="image/png",
                headers={"Cache-Control": "no-store"},
            )
        except (ValueError, OSError, RuntimeError) as exc:
            raise HTTPException(422, str(exc)) from exc

    @router.post("/assets")
    async def upload(request: Request) -> dict[str, str]:
        content = bytearray()
        async for chunk in request.stream():
            content.extend(chunk)
            if len(content) > 20 * 1024 * 1024:
                raise HTTPException(413, "画像は20MB以下にしてください")
        try:
            return {
                "id": await asyncio.to_thread(service.upload, bytes(content))
            }
        except (ValueError, OSError) as exc:
            raise HTTPException(
                422, "画像を読み込めません。PNG・JPEG・WebPを選択してください"
            ) from exc

    @router.post("/assets/delete")
    async def delete(request: DeleteRequest) -> dict[str, str]:
        try:
            await asyncio.to_thread(
                service.delete, request.asset_id, request.draft
            )
            return {"status": "ok"}
        except (ValueError, OSError) as exc:
            raise HTTPException(409, str(exc)) from exc

    @router.get("/assets/{asset_id:path}")
    async def image(asset_id: str) -> FileResponse:
        if not any(
            a["id"] == asset_id
            for a in await asyncio.to_thread(service.catalog)
        ):
            raise HTTPException(404, "素材が見つかりません")
        return FileResponse(
            service.assets.path(asset_id),
            headers={"Cache-Control": "no-store"},
        )

    return router
