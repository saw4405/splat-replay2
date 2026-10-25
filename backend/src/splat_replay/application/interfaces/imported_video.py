"""持込動画の永続化・フレーム入力ポート。"""

from __future__ import annotations

from collections.abc import AsyncIterable, AsyncIterator
from pathlib import Path
from datetime import date, time
from dataclasses import dataclass
from typing import Protocol

from splat_replay.application.dto.imported_video import (
    ImportedBattleDTO,
    ImportedVideoInfo,
    ImportedVideoJobDTO,
)
from splat_replay.domain.models import Frame, VideoAsset
from splat_replay.application.interfaces.weapon_detection import (
    WeaponRecognitionPort,
)


class ImportedVideoRepositoryPort(Protocol):
    """持込ジョブを通常録画キューから分離して保存する。"""

    async def create_job(
        self,
        source_name: str,
        suffix: str,
        chunks: AsyncIterable[bytes],
    ) -> ImportedVideoJobDTO: ...

    def get_job(self, job_id: str) -> ImportedVideoJobDTO | None: ...

    def list_jobs(self) -> list[ImportedVideoJobDTO]: ...

    def save_job(self, job: ImportedVideoJobDTO) -> None: ...

    def save_candidate_metadata(
        self, job_id: str, candidate: ImportedBattleDTO
    ) -> None: ...

    def save_candidate_subtitle(
        self,
        job: ImportedVideoJobDTO,
        candidate: ImportedBattleDTO,
        subtitle: str | None,
    ) -> None: ...

    def save_evidence_frame(
        self, job_id: str, staging: Path, kind: str, frame: Frame
    ) -> None: ...

    def source_path(self, job_id: str) -> Path: ...

    def create_work_directory(self, job_id: str, prefix: str) -> Path: ...

    def candidate_staging_directory(
        self, job_id: str, candidate_id: str
    ) -> Path: ...

    def commit_candidate(
        self,
        job_id: str,
        candidate: ImportedBattleDTO,
        candidate_id: str,
        staging: Path,
    ) -> None: ...

    def remove_work_directory(self, path: Path) -> None: ...

    def remove_candidate_staging_directory(self, path: Path) -> None: ...

    def commit_output(
        self, job_id: str, staging: Path, metadata: dict[str, object]
    ) -> str: ...

    def write_staging_file(
        self, job_id: str, directory: Path, name: str, content: bytes | str
    ) -> None: ...

    def read_asset_text(self, job_id: str, asset: str) -> str | None: ...

    def write_asset(
        self, job_id: str, asset: str, content: bytes | str
    ) -> None: ...

    def move_staging_file(
        self, job_id: str, directory: Path, name: str, destination_name: str
    ) -> None: ...

    def remove_staging_file(
        self, job_id: str, directory: Path, name: str
    ) -> None: ...

    def asset_path(self, job_id: str, asset: str) -> Path | None: ...


class ImportedVideoFrameReaderPort(Protocol):
    """動画を時間順に一定間隔で読み込む。"""

    def frames(
        self, path: Path, sample_interval_seconds: float
    ) -> AsyncIterator[tuple[float, Frame]]: ...


class ImportedVideoProbePort(Protocol):
    """持込動画の長さ・映像・音声ストリームを確認する。"""

    async def inspect_imported_video(
        self, path: Path
    ) -> ImportedVideoInfo: ...


class ImportedVideoWeaponRecognitionFactoryPort(Protocol):
    """持込処理専用の独立したブキ認識器を生成する。"""

    def create(self) -> WeaponRecognitionPort: ...


@dataclass(frozen=True)
class ImportedVideoRenderResult:
    title: str
    description: str
    thumbnail: bytes | None
    subtitle: str | None


class ImportedVideoRendererPort(Protocol):
    async def render(
        self, target: Path, group: list[VideoAsset], day: date, time_slot: time
    ) -> ImportedVideoRenderResult: ...
