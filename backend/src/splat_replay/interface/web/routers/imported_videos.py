"""個人動画の取込・候補確認・編集 API。"""

from __future__ import annotations

import mimetypes
from pathlib import Path
from urllib.parse import unquote

from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import FileResponse
from pydantic import BaseModel

from splat_replay.application.dto.imported_video import ImportedVideoJobDTO
from splat_replay.application.services.imported_video_service import (
    ImportedVideoService,
)
from splat_replay.interface.web.converters.subtitle_dto_converter import (
    to_application_subtitle_data,
    to_interface_subtitle_data,
)
from splat_replay.interface.web.schemas import SubtitleData


class SelectionRequest(BaseModel):
    candidate_ids: list[str]


class CandidateUpdateRequest(BaseModel):
    metadata: dict[str, object] | None = None
    title: str | None = None
    description: str | None = None


class SourceTimeRequest(BaseModel):
    started_at: str


class JobTextRequest(BaseModel):
    title: str
    description: str


def create_imported_videos_router(service: ImportedVideoService) -> APIRouter:
    router = APIRouter(prefix="/api/imported-videos", tags=["imported-videos"])

    @router.post("", status_code=status.HTTP_202_ACCEPTED)
    async def create_import(request: Request) -> ImportedVideoJobDTO:
        source_name = unquote(request.headers.get("x-file-name", "video.mp4"))
        suffix = Path(source_name.replace("\\", "/")).suffix.lower()
        try:
            job = await service.create_import(
                source_name, suffix, request.stream()
            )
            return job
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(
                status_code=400, detail="動画を受け取れませんでした。"
            ) from exc

    @router.get("")
    async def list_imports() -> list[ImportedVideoJobDTO]:
        return service.list_jobs()

    @router.get("/{job_id}")
    async def get_import(job_id: str) -> ImportedVideoJobDTO:
        try:
            job = service.get_job(job_id)
        except ValueError as exc:
            raise HTTPException(
                status_code=404, detail="取込ジョブが見つかりません"
            ) from exc
        if job is None:
            raise HTTPException(
                status_code=404, detail="取込ジョブが見つかりません"
            )
        return job

    @router.post("/{job_id}/scan", status_code=status.HTTP_202_ACCEPTED)
    async def retry_scan(job_id: str) -> ImportedVideoJobDTO:
        try:
            job = service.get_job(job_id)
            if job is None:
                raise FileNotFoundError
            if job.candidates:
                raise ValueError("保存済み候補を選択して編集できます")
            service.start_scan(job_id)
            refreshed = service.get_job(job_id)
            if refreshed is None:
                raise FileNotFoundError
            return refreshed
        except FileNotFoundError as exc:
            raise HTTPException(
                status_code=404, detail="取込ジョブが見つかりません"
            ) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @router.post("/{job_id}/cancel")
    async def cancel_import(job_id: str) -> ImportedVideoJobDTO:
        try:
            return await service.cancel(job_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.put("/{job_id}/selection")
    async def update_selection(
        job_id: str, request: SelectionRequest
    ) -> ImportedVideoJobDTO:
        try:
            return service.set_selection(job_id, request.candidate_ids)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.patch("/{job_id}/candidates/{candidate_id}")
    async def update_candidate(
        job_id: str, candidate_id: str, request: CandidateUpdateRequest
    ) -> ImportedVideoJobDTO:
        try:
            return service.update_candidate(
                job_id,
                candidate_id,
                request.metadata,
                request.title,
                request.description,
            )
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get(
        "/{job_id}/candidates/{candidate_id}/subtitle",
        response_model=SubtitleData,
    )
    async def get_candidate_subtitle(
        job_id: str, candidate_id: str
    ) -> SubtitleData:
        try:
            subtitle = service.get_candidate_subtitle(job_id, candidate_id)
            return to_interface_subtitle_data(subtitle)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.put(
        "/{job_id}/candidates/{candidate_id}/subtitle",
        response_model=SubtitleData,
    )
    async def update_candidate_subtitle(
        job_id: str, candidate_id: str, request: SubtitleData
    ) -> SubtitleData:
        try:
            subtitle = service.update_candidate_subtitle(
                job_id,
                candidate_id,
                to_application_subtitle_data(request),
            )
            return to_interface_subtitle_data(subtitle)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.patch("/{job_id}/source-time")
    async def update_source_time(
        job_id: str, request: SourceTimeRequest
    ) -> ImportedVideoJobDTO:
        try:
            return service.update_source_time(job_id, request.started_at)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.patch("/{job_id}/outputs/{output_id}")
    async def update_output(
        job_id: str, output_id: str, request: JobTextRequest
    ) -> ImportedVideoJobDTO:
        try:
            return service.update_output_text(
                job_id, output_id, request.title, request.description
            )
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.patch("/{job_id}")
    async def update_job_text(
        job_id: str, request: JobTextRequest
    ) -> ImportedVideoJobDTO:
        try:
            return service.update_job_text(
                job_id, request.title, request.description
            )
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/{job_id}/edit", status_code=status.HTTP_202_ACCEPTED)
    async def edit_import(job_id: str) -> ImportedVideoJobDTO:
        try:
            service.start_edit(job_id)
            refreshed = service.get_job(job_id)
            if refreshed is None:
                raise FileNotFoundError
            return refreshed
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get("/{job_id}/assets/{asset:path}")
    async def get_import_asset(
        job_id: str, asset: str, download: bool = Query(default=False)
    ) -> FileResponse:
        try:
            path = service.asset_path(job_id, asset.replace("/", ":"))
        except (ValueError, FileNotFoundError) as exc:
            raise HTTPException(
                status_code=404, detail="ファイルが見つかりません"
            ) from exc
        if path is None:
            raise HTTPException(
                status_code=404, detail="ファイルが見つかりません"
            )
        media_type = (
            mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        )
        return FileResponse(
            path,
            media_type=media_type,
            filename=path.name if download else None,
        )

    return router


__all__ = ["create_imported_videos_router"]
