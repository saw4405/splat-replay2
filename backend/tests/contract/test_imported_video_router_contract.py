"""持込動画APIの外部契約テスト。"""

from __future__ import annotations

from collections.abc import AsyncIterable
from dataclasses import replace
from pathlib import Path
from typing import cast

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from splat_replay.application.dto.imported_video import (
    ImportedBattleDTO,
    ImportedVideoOutputDTO,
    ImportJobState,
    ImportedVideoJobDTO,
)
from splat_replay.application.dto.subtitle import (
    SubtitleBlockDTO,
    SubtitleDataDTO,
)
from splat_replay.application.services.imported_video_service import (
    ImportedVideoService,
)
from splat_replay.interface.web.routers.imported_videos import (
    create_imported_videos_router,
)

pytestmark = pytest.mark.contract


def _job(
    *,
    state: ImportJobState = "ready",
    candidates: tuple[ImportedBattleDTO, ...] = (),
) -> ImportedVideoJobDTO:
    return ImportedVideoJobDTO(
        id="job-1",
        source_name="試合.mp4",
        source_suffix=".mp4",
        state=state,
        progress_percent=100.0,
        duration_seconds=20.0,
        has_audio=True,
        candidates=candidates,
        error=None,
        title=None,
        description=None,
        created_at="2026-10-23T00:00:00+09:00",
        has_output=False,
        has_thumbnail=False,
        has_subtitle=False,
    )


class _ImportedVideoServiceStub:
    def __init__(self, asset: Path) -> None:
        self.job = _job()
        self.asset = asset
        self.upload_source_name = ""
        self.upload_suffix = ""
        self.upload_chunks: list[bytes] = []
        self.selected_ids: list[str] = []
        self.asset_requests: list[str] = []
        self.subtitle_data = SubtitleDataDTO(blocks=[], video_duration=9.0)

    async def create_import(
        self,
        source_name: str,
        suffix: str,
        chunks: AsyncIterable[bytes],
    ) -> ImportedVideoJobDTO:
        self.upload_source_name = source_name
        self.upload_suffix = suffix
        async for chunk in chunks:
            self.upload_chunks.append(chunk)
        self.job = replace(
            self.job,
            source_name=source_name,
            source_suffix=suffix,
            state="scanning",
        )
        return self.job

    def list_jobs(self) -> list[ImportedVideoJobDTO]:
        return [self.job]

    def get_job(self, job_id: str) -> ImportedVideoJobDTO | None:
        return self.job if job_id == self.job.id else None

    def set_selection(
        self, job_id: str, candidate_ids: list[str]
    ) -> ImportedVideoJobDTO:
        self.selected_ids = candidate_ids
        candidate = ImportedBattleDTO(
            id="battle-1",
            start_seconds=1.0,
            end_seconds=10.0,
            segments=((1.0, 10.0),),
            selected="battle-1" in candidate_ids,
            metadata={},
            clip_ready=True,
            duration_seconds=9.0,
        )
        self.job = replace(self.job, candidates=(candidate,))
        return self.job

    def start_edit(self, job_id: str) -> None:
        self.job = replace(self.job, state="editing")

    def get_candidate_subtitle(
        self, job_id: str, candidate_id: str
    ) -> SubtitleDataDTO:
        assert job_id == self.job.id and candidate_id == "battle-1"
        return self.subtitle_data

    def update_candidate_subtitle(
        self, job_id: str, candidate_id: str, data: SubtitleDataDTO
    ) -> SubtitleDataDTO:
        assert job_id == self.job.id and candidate_id == "battle-1"
        self.subtitle_data = data
        return data

    def update_source_time(
        self, job_id: str, started_at: str
    ) -> ImportedVideoJobDTO:
        self.job = replace(
            self.job,
            source_started_at=started_at,
            source_started_at_inferred=False,
        )
        return self.job

    def update_output_text(
        self, job_id: str, output_id: str, title: str, description: str
    ) -> ImportedVideoJobDTO:
        self.job = replace(
            self.job,
            outputs=(
                ImportedVideoOutputDTO(
                    output_id, title, description, True, False, ("battle-1",)
                ),
            ),
        )
        return self.job

    def asset_path(self, job_id: str, asset: str) -> Path | None:
        self.asset_requests.append(asset)
        if job_id != self.job.id or asset != "source":
            raise ValueError("許可されていないファイルです")
        return self.asset


def _client(service: _ImportedVideoServiceStub) -> TestClient:
    app = FastAPI()
    app.include_router(
        create_imported_videos_router(cast(ImportedVideoService, service))
    )
    return TestClient(app)


def test_upload_stream_decodes_japanese_filename_and_returns_job(
    tmp_path: Path,
) -> None:
    """動画本体はrequest.streamで渡し、日本語名は表示用に復元する。"""
    asset = tmp_path / "source.mp4"
    asset.write_bytes(b"source")
    service = _ImportedVideoServiceStub(asset)

    with _client(service) as client:
        response = client.post(
            "/api/imported-videos",
            content=b"video-part-1video-part-2",
            headers={
                "content-type": "application/octet-stream",
                "x-file-name": "%E8%A9%A6%E5%90%88.mp4",
            },
        )

    assert response.status_code == status.HTTP_202_ACCEPTED
    assert response.json()["source_name"] == "試合.mp4"
    assert response.json()["state"] == "scanning"
    assert service.upload_source_name == "試合.mp4"
    assert service.upload_suffix == ".mp4"
    assert b"".join(service.upload_chunks) == b"video-part-1video-part-2"


def test_selection_and_edit_endpoints_preserve_job_contract(
    tmp_path: Path,
) -> None:
    """選択IDを保存し、編集開始後のJob DTOを返す。"""
    asset = tmp_path / "source.mp4"
    asset.write_bytes(b"source")
    service = _ImportedVideoServiceStub(asset)

    with _client(service) as client:
        selection = client.put(
            "/api/imported-videos/job-1/selection",
            json={"candidate_ids": ["battle-1"]},
        )
        edit = client.post("/api/imported-videos/job-1/edit")

    assert selection.status_code == status.HTTP_200_OK
    assert selection.json()["candidates"][0]["selected"] is True
    assert service.selected_ids == ["battle-1"]
    assert edit.status_code == status.HTTP_202_ACCEPTED
    assert edit.json()["state"] == "editing"


def test_asset_download_serves_only_repository_allowed_assets(
    tmp_path: Path,
) -> None:
    """許可assetは取得でき、許可外パスは404で拒否する。"""
    asset = tmp_path / "source.mp4"
    asset.write_bytes(b"source-bytes")
    service = _ImportedVideoServiceStub(asset)

    with _client(service) as client:
        allowed = client.get(
            "/api/imported-videos/job-1/assets/source",
            params={"download": "true"},
        )
        rejected = client.get(
            "/api/imported-videos/job-1/assets/%2E%2E%2Foutside"
        )

    assert allowed.status_code == status.HTTP_200_OK
    assert allowed.content == b"source-bytes"
    assert allowed.headers["content-disposition"] == (
        'attachment; filename="source.mp4"'
    )
    assert rejected.status_code == status.HTTP_404_NOT_FOUND
    assert service.asset_requests == ["source", "..:outside"]


def test_candidate_subtitle_get_and_update_use_structured_seconds_contract(
    tmp_path: Path,
) -> None:
    asset = tmp_path / "source.mp4"
    asset.write_bytes(b"source")
    service = _ImportedVideoServiceStub(asset)
    service.job = replace(
        service.job,
        candidates=(
            ImportedBattleDTO(
                id="battle-1",
                start_seconds=1.0,
                end_seconds=10.0,
                segments=((1.0, 10.0),),
                selected=True,
                metadata={},
                clip_ready=True,
                duration_seconds=9.0,
            ),
        ),
    )

    with _client(service) as client:
        fetched = client.get(
            "/api/imported-videos/job-1/candidates/battle-1/subtitle"
        )
        updated = client.put(
            "/api/imported-videos/job-1/candidates/battle-1/subtitle",
            json={
                "blocks": [
                    {
                        "index": 1,
                        "start_time": 1.25,
                        "end_time": 2.5,
                        "text": "字幕",
                    }
                ],
                "video_duration": 9.0,
            },
        )

    assert fetched.status_code == status.HTTP_200_OK
    assert fetched.json() == {"blocks": [], "video_duration": 9.0}
    assert updated.status_code == status.HTTP_200_OK
    assert updated.json()["blocks"] == [
        {"index": 1, "start_time": 1.25, "end_time": 2.5, "text": "字幕"}
    ]
    assert service.subtitle_data.blocks == [
        SubtitleBlockDTO(1, 1.25, 2.5, "字幕")
    ]


def test_source_time_and_group_output_edit_contract(tmp_path: Path) -> None:
    asset = tmp_path / "source.mp4"
    asset.write_bytes(b"source")
    service = _ImportedVideoServiceStub(asset)
    with _client(service) as client:
        response = client.patch(
            "/api/imported-videos/job-1/source-time",
            json={"started_at": "2026-10-24T10:30"},
        )
        assert response.status_code == 200
        assert response.json()["source_started_at"] == "2026-10-24T10:30"
        assert response.json()["source_started_at_inferred"] is False
        response = client.patch(
            "/api/imported-videos/job-1/outputs/output-1",
            json={"title": "修正後", "description": "説明"},
        )
        assert response.status_code == 200
        assert response.json()["outputs"] == [
            {
                "id": "output-1",
                "title": "修正後",
                "description": "説明",
                "has_thumbnail": True,
                "has_subtitle": False,
                "candidate_ids": ["battle-1"],
            }
        ]


def test_job_response_contains_saved_output_directory(tmp_path: Path) -> None:
    service = _ImportedVideoServiceStub(tmp_path / "video.mp4")
    service.job = replace(
        service.job, output_directory=str(tmp_path / "outputs")
    )
    app = FastAPI()
    app.include_router(
        create_imported_videos_router(cast(ImportedVideoService, service))
    )
    response = TestClient(app).get("/api/imported-videos/job-1")
    assert response.status_code == 200
    assert response.json()["output_directory"] == str(tmp_path / "outputs")
