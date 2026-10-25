"""持込動画専用のファイル保存先。通常の録画・投稿キューとは分離する。"""

from __future__ import annotations

import asyncio
import json
import os
import re
import shutil

import cv2
from collections.abc import AsyncIterable
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

from splat_replay.domain.models import Frame
from splat_replay.infrastructure.adapters.medal_detection.recognizer import (
    MEDAL_ROI,
)
from splat_replay.infrastructure.adapters.weapon_detection.constants import (
    SLOT_BOXES,
)

from splat_replay.application.dto.imported_video import (
    ImportedBattleDTO,
    ImportedVideoOutputDTO,
    ImportedVideoJobDTO,
)

from splat_replay.infrastructure.repositories.imported_video_evidence import (
    build_evidence_annotations,
    parse_evidence_annotations,
)


_ALLOWED_SUFFIXES = {".mp4", ".mov", ".mkv", ".m4v", ".avi", ".webm"}


class FileImportedVideoRepository:
    """base_dir/imports のみを扱う小さなジョブリポジトリ。"""

    def __init__(self, base_dir: Path) -> None:
        self.root = base_dir / "imports"
        self.root.mkdir(parents=True, exist_ok=True)

    async def create_job(
        self,
        source_name: str,
        suffix: str,
        chunks: AsyncIterable[bytes],
    ) -> ImportedVideoJobDTO:
        safe_suffix = suffix.lower()
        if safe_suffix not in _ALLOWED_SUFFIXES:
            raise ValueError("対応していない動画形式です")
        job_id = str(uuid4())
        directory = self.root / job_id
        directory.mkdir()
        source = directory / f"source{safe_suffix}"
        temporary = directory / f".{source.name}.uploading"
        total_bytes = 0
        try:
            with temporary.open("xb") as stream:
                async for chunk in chunks:
                    if chunk:
                        total_bytes += len(chunk)
                        await asyncio.to_thread(stream.write, chunk)
                await asyncio.to_thread(stream.flush)
            if total_bytes == 0:
                raise ValueError("動画ファイルが空です")
            temporary.replace(source)
        except BaseException:
            shutil.rmtree(directory, ignore_errors=True)
            raise
        clean_name = Path(source_name.replace("\\", "/")).name or source.name
        job = ImportedVideoJobDTO(
            id=job_id,
            source_name=clean_name,
            source_suffix=safe_suffix,
            state="queued",
            progress_percent=0.0,
            duration_seconds=None,
            has_audio=None,
            candidates=(),
            error=None,
            title=None,
            description=None,
            created_at=datetime.now(timezone.utc).isoformat(),
            has_output=False,
            has_thumbnail=False,
            has_subtitle=False,
        )
        self.save_job(job)
        return job

    def get_job(self, job_id: str) -> ImportedVideoJobDTO | None:
        try:
            directory = self._job_dir(job_id)
            manifest = self._inside_job(job_id, directory / "manifest.json")
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            candidates = tuple(
                self._candidate_from_dict(item)
                for item in payload.get("candidates", [])
            )
            job = ImportedVideoJobDTO(
                id=job_id,
                source_name=str(payload["source_name"]),
                source_suffix=str(payload["source_suffix"]),
                state=payload["state"],
                progress_percent=float(payload.get("progress_percent", 0)),
                duration_seconds=payload.get("duration_seconds"),
                has_audio=payload.get("has_audio"),
                candidates=candidates,
                error=payload.get("error"),
                title=payload.get("title"),
                description=payload.get("description"),
                created_at=str(payload["created_at"]),
                has_output=bool(payload.get("has_output", False)),
                has_thumbnail=bool(payload.get("has_thumbnail", False)),
                has_subtitle=bool(payload.get("has_subtitle", False)),
                output_id=payload.get("output_id"),
                outputs=tuple(
                    ImportedVideoOutputDTO(
                        id=str(item["id"]),
                        title=str(item.get("title", "")),
                        description=str(item.get("description", "")),
                        has_thumbnail=bool(item.get("has_thumbnail")),
                        has_subtitle=bool(item.get("has_subtitle")),
                        candidate_ids=tuple(
                            str(value)
                            for value in item.get("candidate_ids", [])
                        ),
                    )
                    for item in payload.get("outputs", [])
                ),
                source_started_at=payload.get("source_started_at"),
                source_started_at_inferred=bool(
                    payload.get("source_started_at_inferred", False)
                ),
            )
            recovered = self._recover_committed(job)
            output_ids = tuple(output.id for output in recovered.outputs)
            if recovered.output_id:
                output_ids += (recovered.output_id,)
            has_saved_video = any(
                self.asset_path(job_id, f"output:{output_id}:video.mp4")
                is not None
                for output_id in output_ids
            )
            return replace(
                recovered,
                output_directory=str((directory / "outputs").resolve())
                if has_saved_video
                else None,
            )
        except (FileNotFoundError, KeyError, ValueError, TypeError, OSError):
            return None

    def list_jobs(self) -> list[ImportedVideoJobDTO]:
        jobs = [
            job
            for path in self.root.iterdir()
            if path.is_dir() and (job := self.get_job(path.name)) is not None
        ]
        return sorted(jobs, key=lambda job: job.created_at, reverse=True)

    def save_job(self, job: ImportedVideoJobDTO) -> None:
        payload = asdict(job)
        payload.pop("output_directory", None)
        temporary = self._job_dir(job.id) / f".manifest-{uuid4().hex}.tmp"
        with temporary.open("x", encoding="utf-8") as stream:
            stream.write(
                json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
            )
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(self._job_dir(job.id) / "manifest.json")

    def save_candidate_metadata(
        self, job_id: str, candidate: ImportedBattleDTO
    ) -> None:
        target = self._asset_target(
            job_id, f"candidate:{candidate.id}:metadata.json"
        )
        checkpoint = self._inside_job(job_id, target.parent / "candidate.json")
        if not checkpoint.is_file():
            raise FileNotFoundError("候補情報が見つかりません")
        self._write_atomic_json(target, candidate.metadata)
        self._write_atomic_json(checkpoint, asdict(candidate))

    def save_candidate_subtitle(
        self,
        job: ImportedVideoJobDTO,
        candidate: ImportedBattleDTO,
        subtitle: str | None,
    ) -> None:
        candidate_id = self._validate_id(candidate.id)
        if candidate.id != candidate_id or not any(
            item.id == candidate_id for item in job.candidates
        ):
            raise ValueError("字幕の保存対象が取込ジョブにありません")
        directory = self._job_dir(job.id)
        candidate_dir = self._inside_job(
            job.id, directory / "candidates" / candidate_id
        )
        if not candidate_dir.is_dir():
            raise FileNotFoundError("保存済みの候補動画がありません")
        subtitle_path = self._asset_target(
            job.id, f"candidate:{candidate_id}:subtitle.srt"
        )
        checkpoint = self._inside_job(job.id, candidate_dir / "candidate.json")
        if not checkpoint.is_file():
            raise FileNotFoundError("候補情報が見つかりません")

        if subtitle is None:
            subtitle_path.unlink(missing_ok=True)
        else:
            self._write_atomic_content(subtitle_path, subtitle)
        self._write_atomic_json(checkpoint, asdict(candidate))
        self.save_job(job)

    def save_evidence_frame(
        self, job_id: str, staging: Path, kind: str, frame: Frame
    ) -> None:
        if kind not in {
            "weapons",
            "result",
            "judgement",
            "result-full",
            "rate",
            "match_select",
        }:
            raise ValueError("不正な確認画像です")
        # 認識器と同じ1920x1080座標で、実際に採用したフレームだけを切り出す。
        image = cv2.resize(frame, (1920, 1080))
        boxes = {
            "weapons": (500, 10, 1420, 130),
            "result": (1000, 250, 1800, 450),
            "judgement": (0, 0, 340, 200),
        }
        if kind in boxes:
            x1, y1, x2, y2 = boxes[kind]
            image = image[y1:y2, x1:x2]
        success, encoded = cv2.imencode(".png", image)
        if not success:
            raise ValueError("確認画像を保存できません")
        self.write_staging_file(
            job_id, staging, f"{kind}.png", encoded.tobytes()
        )

    def _weapon_slot_evidence(self, job_id: str, directory: Path) -> None:
        weapons = self._inside_job(job_id, directory / "weapons.png")
        targets = {
            slot: self._inside_job(job_id, directory / f"weapons_{slot}.png")
            for slot in SLOT_BOXES
        }
        if not weapons.is_file() or all(
            target.is_file() for target in targets.values()
        ):
            return
        image = cv2.imread(str(weapons))
        if image is None or image.shape[:2] != (120, 920):
            return
        # 保存済みの採用画像を再利用し、認識器のslot座標だけを正とする。
        for slot, (x1, y1, x2, y2) in SLOT_BOXES.items():
            target = targets[slot]
            if target.is_file():
                continue
            success, encoded = cv2.imencode(
                ".png", image[y1 - 10 : y2 - 10, x1 - 500 : x2 - 500]
            )
            if not success:
                raise ValueError("ブキ確認画像を保存できません")
            self._write_atomic_content(target, encoded.tobytes())

    def _medal_evidence(self, job_id: str, directory: Path) -> None:
        target = self._inside_job(job_id, directory / "medals.png")
        source = self._inside_job(job_id, directory / "result-full.png")
        if target.is_file() or not source.is_file():
            return
        image = cv2.imread(str(source))
        if image is None or image.shape[:2] != (1080, 1920):
            return
        x1, y1, x2, y2 = MEDAL_ROI
        success, encoded = cv2.imencode(".png", image[y1:y2, x1:x2])
        if not success:
            raise ValueError("表彰確認画像を保存できません")
        self._write_atomic_content(target, encoded.tobytes())

    def source_path(self, job_id: str) -> Path:
        job = self.get_job(job_id)
        if job is None:
            raise FileNotFoundError("取込ジョブが見つかりません")
        if job.source_suffix not in _ALLOWED_SUFFIXES:
            raise ValueError("保存済み動画形式が不正です")
        return self._inside_job(
            job_id, self._job_dir(job_id) / f"source{job.source_suffix}"
        )

    def create_work_directory(self, job_id: str, prefix: str) -> Path:
        if prefix not in {"work", "output"}:
            raise ValueError("不正な作業ディレクトリ名です")
        directory = self._job_dir(job_id) / f".{prefix}-{uuid4().hex}"
        directory.mkdir()
        return self._inside_job(job_id, directory)

    def candidate_staging_directory(
        self, job_id: str, candidate_id: str
    ) -> Path:
        candidate_id = self._validate_id(candidate_id)
        job_root = self._job_dir(job_id)
        staging_parent = job_root / ".candidates"
        self._ensure_job_directory(job_id, ".candidates")
        staging = staging_parent / candidate_id
        staging.mkdir(parents=True, exist_ok=False)
        return self._inside_job(job_id, staging)

    def commit_candidate(
        self,
        job_id: str,
        candidate: ImportedBattleDTO,
        candidate_id: str,
        staging: Path,
    ) -> None:
        candidate_id = self._validate_id(candidate_id)
        if candidate.id != candidate_id:
            raise ValueError("候補IDと保存内容が一致しません")
        job_root = self._job_dir(job_id)
        target_parent = job_root / "candidates"
        self._ensure_job_directory(job_id, "candidates")
        target = target_parent / candidate_id
        safe_staging = self._staging_dir(job_id, staging)
        if (
            safe_staging.parent != (job_root / ".candidates").resolve()
            or safe_staging.name != candidate_id
        ):
            raise ValueError("候補の一時フォルダが一致しません")
        if target.exists():
            raise FileExistsError("候補動画は既に保存されています")
        self._inside_job(job_id, target)
        self._write_json(safe_staging / "candidate.json", asdict(candidate))
        safe_staging.replace(target)

    def remove_work_directory(self, path: Path) -> None:
        job_id = path.parent.name
        if not path.name.startswith((".work-", ".output-")):
            raise ValueError("作業ディレクトリではありません")
        resolved = self._staging_dir(job_id, path)
        shutil.rmtree(resolved, ignore_errors=True)

    def remove_candidate_staging_directory(self, path: Path) -> None:
        if path.parent.name != ".candidates":
            raise ValueError("候補の一時ディレクトリではありません")
        job_id = path.parent.parent.name
        resolved = self._staging_dir(job_id, path)
        self._validate_id(resolved.name)
        if (
            resolved.parent
            != (self._job_dir(job_id) / ".candidates").resolve()
        ):
            raise ValueError("候補の一時ディレクトリが不正です")
        shutil.rmtree(resolved, ignore_errors=True)

    def commit_output(
        self, job_id: str, staging: Path, metadata: dict[str, object]
    ) -> str:
        job_root = self._job_dir(job_id)
        outputs = job_root / "outputs"
        self._ensure_job_directory(job_id, "outputs")
        output_id = str(uuid4())
        target = outputs / output_id
        if target.exists():
            raise FileExistsError("編集済み動画の保存先が既にあります")
        self._inside_job(job_id, target)
        safe_staging = self._staging_dir(job_id, staging)
        if (
            safe_staging.parent != job_root.resolve()
            or not safe_staging.name.startswith(".output-")
        ):
            raise ValueError("編集結果の一時フォルダが不正です")
        self._write_json(
            safe_staging / "output.json",
            {**metadata, "output_id": output_id},
        )
        safe_staging.replace(target)
        return output_id

    def write_staging_file(
        self, job_id: str, directory: Path, name: str, content: bytes | str
    ) -> None:
        staging = self._staging_dir(job_id, directory)
        target = staging / self._allowed_staging_name(name)
        self._inside_job(job_id, target)
        self._write_content(target, content)

    def read_asset_text(self, job_id: str, asset: str) -> str | None:
        path = self.asset_path(job_id, asset)
        if path is None:
            return None
        return path.read_text(encoding="utf-8")

    def write_asset(
        self, job_id: str, asset: str, content: bytes | str
    ) -> None:
        target = self._asset_target(job_id, asset)
        self._inside_job(job_id, target)
        self._write_content(target, content)

    def move_staging_file(
        self, job_id: str, directory: Path, name: str, destination_name: str
    ) -> None:
        staging = self._staging_dir(job_id, directory)
        source = self._inside_job(
            job_id, staging / self._allowed_staging_name(name)
        )
        destination = self._inside_job(
            job_id, staging / self._allowed_staging_name(destination_name)
        )
        source.replace(destination)

    def remove_staging_file(
        self, job_id: str, directory: Path, name: str
    ) -> None:
        staging = self._staging_dir(job_id, directory)
        path = self._inside_job(
            job_id, staging / self._allowed_staging_name(name)
        )
        path.unlink(missing_ok=True)

    def asset_path(self, job_id: str, asset: str) -> Path | None:
        directory = self._job_dir(job_id)
        parts = asset.split(":")
        if parts == ["source"]:
            path = self.source_path(job_id)
        elif parts[0] == "output" and len(parts) == 3:
            output_id = parts[1]
            if output_id == "latest":
                job = self.get_job(job_id)
                output_id = job.output_id if job is not None else ""
            if not output_id:
                raise ValueError("編集済みファイルが見つかりません")
            output_id = self._validate_id(output_id)
            path = self._asset_target(job_id, f"output:{output_id}:{parts[2]}")
        elif parts[0] == "candidate" and len(parts) == 3:
            candidate_id = self._validate_id(parts[1])
            path = self._asset_target(
                job_id, f"candidate:{candidate_id}:{parts[2]}"
            )
        else:
            raise ValueError("不正なアセット指定です")
        resolved = path.resolve()
        if not resolved.is_relative_to(directory.resolve()):
            raise ValueError("アセットが取込フォルダ外を指しています")
        return resolved if resolved.is_file() else None

    def _asset_target(self, job_id: str, asset: str) -> Path:
        directory = self._job_dir(job_id)
        parts = asset.split(":")
        if parts == ["source"]:
            job = self.get_job(job_id)
            if job is None or job.source_suffix not in _ALLOWED_SUFFIXES:
                raise ValueError("保存済み動画形式が不正です")
            target = directory / f"source{job.source_suffix}"
        elif parts[0] == "output" and len(parts) == 3:
            output_id = self._validate_id(parts[1])
            target = (
                directory
                / "outputs"
                / output_id
                / self._allowed_asset_name(parts[2])
            )
        elif parts[0] == "candidate" and len(parts) == 3:
            candidate_id = self._validate_id(parts[1])
            target = (
                directory
                / "candidates"
                / candidate_id
                / self._allowed_asset_name(parts[2])
            )
        else:
            raise ValueError("不正なアセット指定です")
        return self._inside_job(job_id, target)

    def _staging_dir(self, job_id: str, directory: Path) -> Path:
        safe = self._inside_job(job_id, directory)
        job_root = self._job_dir(job_id).resolve()
        is_candidate = safe.parent == (job_root / ".candidates").resolve()
        is_work = safe.parent == job_root and safe.name.startswith(
            (".work-", ".output-")
        )
        if not (is_candidate or is_work) or not safe.is_dir():
            raise ValueError("取込ジョブの作業フォルダではありません")
        return safe

    def _ensure_job_directory(self, job_id: str, name: str) -> Path:
        if name not in {".candidates", "candidates", "outputs"}:
            raise ValueError("不正な取込フォルダ名です")
        target = self._job_dir(job_id) / name
        if target.is_symlink():
            self._inside_job(job_id, target)
        target.mkdir(exist_ok=True)
        return self._inside_job(job_id, target)

    @staticmethod
    def _allowed_staging_name(name: str) -> str:
        if name in {
            "video.mp4",
            "thumbnail.png",
            "weapons.png",
            "result.png",
            "judgement.png",
            "result-full.png",
            "rate.png",
            "match_select.png",
            "medals.png",
            *(f"weapons_{slot}.png" for slot in SLOT_BOXES),
            "metadata.json",
            "subtitle.srt",
            "title.txt",
            "description.txt",
        } or re.fullmatch(r"part-\d+\.mp4", name):
            return name
        raise ValueError("不正な作業ファイル名です")

    @staticmethod
    def _write_json(path: Path, payload: object) -> None:
        with path.open("x", encoding="utf-8") as stream:
            stream.write(
                json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
            )
            stream.flush()
            os.fsync(stream.fileno())

    @staticmethod
    def _write_content(path: Path, content: bytes | str) -> None:
        if isinstance(content, bytes):
            with path.open("wb") as stream:
                stream.write(content)
        else:
            with path.open("w", encoding="utf-8") as stream:
                stream.write(content)

    @staticmethod
    def _write_atomic_content(path: Path, content: bytes | str) -> None:
        temporary = path.parent / f".{path.name}-{uuid4().hex}.tmp"
        try:
            with temporary.open("xb") as stream:
                stream.write(
                    content.encode("utf-8")
                    if isinstance(content, str)
                    else content
                )
                stream.flush()
                os.fsync(stream.fileno())
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)

    @staticmethod
    def _write_atomic_json(path: Path, payload: object) -> None:
        temporary = path.parent / f".{path.name}-{uuid4().hex}.tmp"
        try:
            with temporary.open("x", encoding="utf-8") as stream:
                stream.write(
                    json.dumps(
                        payload, ensure_ascii=False, separators=(",", ":")
                    )
                )
                stream.flush()
                os.fsync(stream.fileno())
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)

    @staticmethod
    def _candidate_from_dict(item: dict[str, object]) -> ImportedBattleDTO:
        raw_start = item.get("start_seconds")
        raw_end = item.get("end_seconds")
        raw_segments = item.get("segments")
        raw_metadata = item.get("metadata", {})
        if not isinstance(raw_start, (int, float)) or not isinstance(
            raw_end, (int, float)
        ):
            raise ValueError("候補の時刻情報が不正です")
        if not isinstance(raw_segments, list):
            raise ValueError("候補の区間情報が不正です")
        segments: list[tuple[float, float]] = []
        for segment in raw_segments:
            if not isinstance(segment, list) or len(segment) != 2:
                raise ValueError("候補の区間情報が不正です")
            start, end = segment
            if not isinstance(start, (int, float)) or not isinstance(
                end, (int, float)
            ):
                raise ValueError("候補の区間情報が不正です")
            segments.append((float(start), float(end)))
        if not isinstance(raw_metadata, dict):
            raise ValueError("候補のメタデータが不正です")
        metadata: dict[str, object] = {}
        for key, value in raw_metadata.items():
            if not isinstance(key, str):
                raise ValueError("候補のメタデータが不正です")
            metadata[key] = value
        title = item.get("title")
        description = item.get("description")
        if title is not None and not isinstance(title, str):
            raise ValueError("候補のタイトルが不正です")
        if description is not None and not isinstance(description, str):
            raise ValueError("候補の説明が不正です")
        raw_duration = item.get("duration_seconds", 0.0)
        if not isinstance(raw_duration, (int, float)):
            raise ValueError("候補の動画長が不正です")
        raw_assets = item.get("evidence_assets", {})
        raw_seconds = item.get("evidence_seconds", {})
        if not isinstance(raw_assets, dict) or not isinstance(
            raw_seconds, dict
        ):
            raise ValueError("候補の確認画像情報が不正です")
        evidence_assets = {
            str(key): str(value) for key, value in raw_assets.items()
        }
        evidence_seconds = {
            str(key): float(value)
            for key, value in raw_seconds.items()
            if isinstance(value, (int, float))
        }
        evidence_regions, evidence_sizes = parse_evidence_annotations(item)
        return ImportedBattleDTO(
            id=str(item["id"]),
            start_seconds=float(raw_start),
            end_seconds=float(raw_end),
            segments=tuple(segments),
            selected=bool(item.get("selected", True)),
            metadata=metadata,
            title=title,
            description=description,
            clip_ready=bool(item.get("clip_ready", False)),
            duration_seconds=float(raw_duration),
            has_thumbnail=bool(item.get("has_thumbnail", False)),
            has_subtitle=bool(item.get("has_subtitle", False)),
            evidence_assets=evidence_assets,
            evidence_seconds=evidence_seconds,
            evidence_regions=evidence_regions,
            evidence_sizes=evidence_sizes,
        )

    def _recover_committed(
        self, job: ImportedVideoJobDTO
    ) -> ImportedVideoJobDTO:
        job_root = self._job_dir(job.id)
        known = {candidate.id for candidate in job.candidates}
        recovered = list(job.candidates)
        candidates_dir = job_root / "candidates"
        if candidates_dir.is_dir():
            self._inside_job(job.id, candidates_dir)
            for folder in candidates_dir.iterdir():
                try:
                    candidate_id = self._validate_id(folder.name)
                    safe_folder = self._inside_job(job.id, folder)
                    marker = self._inside_job(
                        job.id, safe_folder / "candidate.json"
                    )
                    if candidate_id in known or not marker.is_file():
                        continue
                    candidate = self._candidate_from_dict(
                        json.loads(marker.read_text(encoding="utf-8"))
                    )
                    if candidate.id == candidate_id:
                        recovered.append(candidate)
                        known.add(candidate_id)
                except (
                    OSError,
                    ValueError,
                    KeyError,
                    TypeError,
                    json.JSONDecodeError,
                ):
                    continue
        if tuple(recovered) != job.candidates:
            job = replace(
                job,
                candidates=tuple(
                    sorted(recovered, key=lambda c: c.start_seconds)
                ),
            )

        latest_output: tuple[str, dict[str, object]] | None = None
        recovered_outputs: list[tuple[str, ImportedVideoOutputDTO]] = []
        outputs = job_root / "outputs"
        if outputs.is_dir():
            self._inside_job(job.id, outputs)
            for folder in outputs.iterdir():
                try:
                    output_id = self._validate_id(folder.name)
                    safe_folder = self._inside_job(job.id, folder)
                    marker = self._inside_job(
                        job.id, safe_folder / "output.json"
                    )
                    if not marker.is_file():
                        continue
                    metadata = json.loads(marker.read_text(encoding="utf-8"))
                    if metadata.get("output_id") != output_id:
                        continue
                    marker_created = str(metadata.get("created_at", ""))
                    title_path = safe_folder / "title.txt"
                    description_path = safe_folder / "description.txt"
                    title = (
                        title_path.read_text(encoding="utf-8")
                        if title_path.is_file()
                        else str(metadata.get("title", ""))
                    )
                    description = (
                        description_path.read_text(encoding="utf-8")
                        if description_path.is_file()
                        else str(metadata.get("description", ""))
                    )
                    metadata["title"], metadata["description"] = (
                        title,
                        description,
                    )
                    recovered_outputs.append(
                        (
                            marker_created,
                            ImportedVideoOutputDTO(
                                id=output_id,
                                title=title,
                                description=description,
                                has_thumbnail=bool(
                                    metadata.get("has_thumbnail")
                                ),
                                has_subtitle=bool(
                                    metadata.get("has_subtitle")
                                ),
                                candidate_ids=tuple(
                                    str(value)
                                    for value in metadata.get(
                                        "candidate_ids", []
                                    )
                                ),
                            ),
                        )
                    )
                    if latest_output is None or marker_created > str(
                        latest_output[1].get("created_at", "")
                    ):
                        latest_output = output_id, metadata
                except (OSError, ValueError, TypeError, json.JSONDecodeError):
                    continue
        if recovered_outputs:
            job = replace(
                job,
                outputs=tuple(
                    item
                    for _, item in sorted(
                        recovered_outputs, key=lambda pair: pair[0]
                    )
                ),
            )
        if latest_output is not None:
            output_id, metadata = latest_output
            if output_id != job.output_id or not job.has_output:
                job = replace(
                    job,
                    state=job.state
                    if job.state in {"editing", "scanning"}
                    else "completed",
                    progress_percent=100.0,
                    has_output=True,
                    has_thumbnail=bool(metadata.get("has_thumbnail")),
                    has_subtitle=bool(metadata.get("has_subtitle")),
                    output_id=output_id,
                    title=metadata.get("title"),
                    description=metadata.get("description"),
                    error=None,
                )
        candidates: list[ImportedBattleDTO] = []
        repaired = False
        for candidate in job.candidates:
            candidate_id = self._validate_id(candidate.id)
            subtitle_path = self._inside_job(
                job.id, job_root / "candidates" / candidate_id / "subtitle.srt"
            )
            has_subtitle = subtitle_path.is_file()
            directory = self._inside_job(
                job.id, job_root / "candidates" / candidate_id
            )
            for ensure_image in (
                self._weapon_slot_evidence,
                self._medal_evidence,
            ):
                try:
                    ensure_image(job.id, directory)
                except (OSError, ValueError, cv2.error):
                    # 任意の確認画像を生成できなくても保存済み候補は読み出す。
                    pass
            assets = dict(candidate.evidence_assets)
            seconds = dict(candidate.evidence_seconds)
            names = {
                "result_full": "result-full.png",
                "medals": "medals.png",
                "rate": "rate.png",
                "match_select": "match_select.png",
                **{
                    f"weapons_{slot}": f"weapons_{slot}.png"
                    for slot in SLOT_BOXES
                },
            }
            for kind, name in names.items():
                try:
                    path = self._inside_job(job.id, directory / name)
                    exists = path.is_file()
                except (OSError, ValueError):
                    continue
                if exists:
                    assets[kind] = f"candidate/{candidate_id}/{name}"
                    source_kind = (
                        "result"
                        if kind in {"result_full", "medals"}
                        else "weapons"
                        if kind.startswith("weapons_")
                        else kind
                    )
                    if source_kind in candidate.evidence_seconds:
                        seconds[kind] = candidate.evidence_seconds[source_kind]
                else:
                    assets.pop(kind, None)
                    seconds.pop(kind, None)
            if "match_select" not in assets and "rate" in assets:
                assets["match_select"] = assets["rate"]
                if "rate" in seconds:
                    seconds["match_select"] = seconds["rate"]
            regions = dict(candidate.evidence_regions)
            sizes = dict(candidate.evidence_sizes)
            missing = {
                kind: self._inside_job(job.id, directory / Path(asset).name)
                for kind, asset in assets.items()
                if kind
                in {"match_select", "weapons", "result_full", "judgement"}
                and (kind not in regions or kind not in sizes)
            }
            try:
                new_regions, new_sizes = build_evidence_annotations(
                    missing, candidate.metadata
                )
                regions.update(new_regions)
                sizes.update(new_sizes)
            except (OSError, ValueError, cv2.error):
                # 確認用の位置測定が失敗しても採用済みの認識値は保持する。
                pass
            updated = replace(
                candidate,
                has_subtitle=has_subtitle,
                evidence_assets=assets,
                evidence_seconds=seconds,
                evidence_regions=regions,
                evidence_sizes=sizes,
            )
            if updated != candidate:
                repaired = True
                checkpoint = self._inside_job(
                    job.id,
                    job_root / "candidates" / candidate_id / "candidate.json",
                )
                if checkpoint.is_file():
                    try:
                        self._write_atomic_json(checkpoint, asdict(updated))
                    except OSError:
                        pass
            candidates.append(updated)
        if tuple(candidates) != job.candidates:
            job = replace(job, candidates=tuple(candidates))
        if repaired:
            try:
                self.save_job(job)
            except OSError:
                pass
        return job

    def _job_dir(self, job_id: str) -> Path:
        job_id = self._validate_id(job_id)
        directory = self.root / job_id
        if not directory.is_dir() or not directory.resolve().is_relative_to(
            self.root.resolve()
        ):
            raise FileNotFoundError("取込ジョブが見つかりません")
        return directory

    def _inside_job(self, job_id: str, path: Path) -> Path:
        job_root = self._job_dir(job_id).resolve()
        resolved = path.resolve()
        if not resolved.is_relative_to(job_root):
            raise ValueError("取込フォルダ外のパスです")
        return resolved

    @staticmethod
    def _validate_id(value: str) -> str:
        try:
            return str(UUID(value))
        except (ValueError, TypeError, AttributeError) as exc:
            raise ValueError("不正な取込IDです") from exc

    @staticmethod
    def _allowed_asset_name(name: str) -> str:
        if name not in {
            "video.mp4",
            "thumbnail.png",
            "weapons.png",
            "result.png",
            "judgement.png",
            "result-full.png",
            "rate.png",
            "match_select.png",
            "medals.png",
            *(f"weapons_{slot}.png" for slot in SLOT_BOXES),
            "metadata.json",
            "subtitle.srt",
            "title.txt",
            "description.txt",
        }:
            raise ValueError("不正なアセット名です")
        return name
