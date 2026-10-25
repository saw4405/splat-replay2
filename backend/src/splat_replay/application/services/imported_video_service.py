"""個人の持込動画を検出・編集し、専用領域へ保存する。"""

from __future__ import annotations

import asyncio
import json
import hashlib
import math
import re
from collections.abc import Mapping, Set
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path
from collections.abc import AsyncIterable
from uuid import uuid4

from splat_replay.application.dto.imported_video import (
    ImportedBattleDTO,
    ImportedVideoOutputDTO,
    ImportedVideoJobDTO,
)
from splat_replay.application.dto.subtitle import (
    SubtitleBlockDTO,
    SubtitleDataDTO,
)
from splat_replay.application.interfaces import (
    EventBusPort,
    EventSubscription,
    FramePreviewPort,
    LoggerPort,
    VideoEditorPort,
    WeaponDisplayDetectionResult,
    WeaponRecognitionPort,
    WeaponRecognitionResult,
    WeaponSlotResult,
)
from splat_replay.application.interfaces.imported_video import (
    ImportedVideoFrameReaderPort,
    ImportedVideoProbePort,
    ImportedVideoRepositoryPort,
    ImportedVideoRendererPort,
    ImportedVideoWeaponRecognitionFactoryPort,
)
from splat_replay.application.metadata import (
    recording_metadata_to_dict,
    BATTLE_METADATA_FIELD_DEFINITIONS,
)
from splat_replay.application.metadata.codec import (
    MISSING,
    parse_metadata_field_update,
)
from splat_replay.domain.exceptions import ValidationError
from splat_replay.application.services.common.subtitle_converter import (
    SubtitleConverter,
)
from splat_replay.application.services.editing.metadata_parser import (
    MetadataParser,
)
from splat_replay.application.services.recording.recording_context import (
    RecordingContext,
)
from splat_replay.application.services.recording.weapon_detection_service import (
    DETECTION_WINDOW_SECONDS,
    SAMPLED_FRAME_INTERVAL_SECONDS,
    WeaponDetectionService,
)
from splat_replay.domain.events import DomainEvent
from splat_replay.domain.models import (
    BattleResult,
    Frame,
    GameMode,
    Judgement,
    RateBase,
    RecordingMetadata,
    VideoAsset,
)
from splat_replay.domain.services import FrameAnalyzer
from splat_replay.application.services.editing.video_grouping_service import (
    VideoGroupingService,
)


_SCAN_INTERVAL_SECONDS = SAMPLED_FRAME_INTERVAL_SECONDS
_UNKNOWN_WEAPONS = ("不明", "不明", "不明", "不明")


class _VideoTimelineClock:
    """既存ブキ認識制御に動画内時刻を供給する。"""

    def __init__(self) -> None:
        self.seconds = 0.0

    def now(self) -> float:
        return self.seconds


class _ImportedVideoEventSink(EventBusPort):
    """持込解析の認識結果を録画UIのイベントへ流さない。"""

    def publish(
        self, event_type: str, payload: Mapping[str, object] | None = None
    ) -> None:
        _ = event_type, payload

    def publish_domain_event(self, event: DomainEvent) -> None:
        _ = event

    def subscribe(
        self, event_types: Set[str] | None = None
    ) -> EventSubscription:
        _ = event_types
        raise RuntimeError("持込解析からのイベント購読は利用できません")


class _ImportedVideoWeaponRecognizer(WeaponRecognitionPort):
    """既存判定を使い、通常録画の診断ファイルだけを出力しない。"""

    def __init__(self, recognizer: WeaponRecognitionPort) -> None:
        self._recognizer = recognizer
        self.evidence_frame: Frame | None = None
        self.evidence_seconds = 0.0
        self.seconds = 0.0
        self.frame_times: dict[bytes, float] = {}
        self._display_quality: dict[bytes, int] = {}
        self._evidence_quality = 0

    def remember_frame(self, frame: Frame, seconds: float) -> None:
        fingerprint = hashlib.blake2b(frame.tobytes(), digest_size=16).digest()
        self.frame_times[fingerprint] = seconds

    def request_cancel(self) -> None:
        self._recognizer.request_cancel()

    async def detect_weapon_display(self, frame: Frame) -> bool:
        visible = await self._recognizer.detect_weapon_display(frame)
        fingerprint = hashlib.blake2b(frame.tobytes(), digest_size=16).digest()
        self._display_quality[fingerprint] = 2 if visible else 0
        return visible

    async def detect_weapon_display_details(
        self, frame: Frame
    ) -> WeaponDisplayDetectionResult:
        details = await self._recognizer.detect_weapon_display_details(frame)
        fingerprint = hashlib.blake2b(frame.tobytes(), digest_size=16).digest()
        self._display_quality[fingerprint] = (
            2 if details.is_visible else 1 if details.should_recognize else 0
        )
        return details

    async def recognize_weapons(
        self,
        frame: Frame,
        save_predict_weapons_output: bool = True,
        target_slots: set[str] | None = None,
        previous_results: dict[str, WeaponSlotResult] | None = None,
        battle_dir_name: str | None = None,
    ) -> WeaponRecognitionResult:
        fingerprint = hashlib.blake2b(frame.tobytes(), digest_size=16).digest()
        quality = self._display_quality.get(fingerprint, 0)
        result = await self._recognizer.recognize_weapons(
            frame,
            save_predict_weapons_output=False,
            target_slots=target_slots,
            previous_results=previous_results,
            battle_dir_name=None,
        )
        # 実際に照合した表示中フレームを優先し、終了時の非表示入力で上書きしない。
        if quality > 0 and quality >= self._evidence_quality:
            self.evidence_frame = frame.copy()
            self.evidence_seconds = self.frame_times.get(
                fingerprint, self.seconds
            )
            self._evidence_quality = quality
        return result

    async def save_predict_weapons_output(
        self,
        frame: Frame,
        slot_results: tuple[WeaponSlotResult, ...],
        battle_dir_name: str | None = None,
    ) -> str | None:
        _ = frame, slot_results, battle_dir_name
        return None


class ImportedVideoService:
    """独立した持込動画ジョブを管理する。"""

    def __init__(
        self,
        repository: ImportedVideoRepositoryPort,
        frame_reader: ImportedVideoFrameReaderPort,
        probe: ImportedVideoProbePort,
        video_editor: VideoEditorPort,
        frame_preview: FramePreviewPort,
        analyzer: FrameAnalyzer,
        subtitle_converter: SubtitleConverter,
        weapon_recognition_factory: ImportedVideoWeaponRecognitionFactoryPort,
        logger: LoggerPort,
        renderer: ImportedVideoRendererPort | None = None,
    ) -> None:
        self.renderer = renderer
        self.repository = repository
        self.frame_reader = frame_reader
        self.probe = probe
        self.video_editor = video_editor
        self.frame_preview = frame_preview
        # FrameAnalyzer/MetadataParserは呼出しごとに状態を書き換えず、
        # 通常録画と共有しても独立した入力を読む。
        self.analyzer = analyzer
        self.subtitle_converter = subtitle_converter
        self.weapon_recognition_factory = weapon_recognition_factory
        self.logger = logger
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._edit_tasks: dict[str, asyncio.Task[ImportedVideoJobDTO]] = {}

    async def create_import(
        self, source_name: str, suffix: str, chunks: AsyncIterable[bytes]
    ) -> ImportedVideoJobDTO:
        job = await self.repository.create_job(source_name, suffix, chunks)
        match = re.search(
            r"(\d{4}-\d{2}-\d{2})[ _](\d{2})[-:](\d{2})[-:](\d{2})",
            source_name,
        )
        if match:
            try:
                started = datetime.fromisoformat(
                    f"{match[1]}T{match[2]}:{match[3]}:{match[4]}"
                )
                job = replace(
                    job,
                    source_started_at=started.isoformat(),
                    source_started_at_inferred=True,
                )
                self.repository.save_job(job)
            except ValueError:
                pass
        self.start_scan(job.id)
        return self._require_job(job.id)

    async def resume_pending(self) -> None:
        """起動時は途中結果だけ復元し、解析や編集を自動再開しない。"""
        for job in self.repository.list_jobs():
            if job.state in {"scanning", "editing"}:
                if job.candidates:
                    self.repository.save_job(
                        replace(
                            job,
                            state="ready",
                            progress_percent=100.0
                            if job.state == "scanning"
                            else job.progress_percent,
                            error="前回の処理は中断しました。保存済み候補を確認して続けてください。",
                        )
                    )
                else:
                    self.repository.save_job(
                        replace(
                            job,
                            state="queued",
                            error="前回の解析は中断しました。動画を選んで解析を再開してください。",
                        )
                    )

    def start_scan(self, job_id: str) -> None:
        job = self._require_job(job_id)
        task = self._tasks.get(job_id)
        if task is not None and not task.done():
            raise ValueError("この動画はすでに処理中です")
        if (
            job.state not in {"queued", "failed", "cancelled"}
            or job.candidates
        ):
            raise ValueError("保存済みの候補を選択して編集できます")
        self.repository.save_job(
            replace(job, state="scanning", progress_percent=0.0, error=None)
        )
        self._tasks[job_id] = asyncio.create_task(self._scan_job(job_id))

    async def wait_for_scan(self, job_id: str) -> ImportedVideoJobDTO:
        task = self._tasks.get(job_id)
        if task is not None:
            await task
        job = self.get_job(job_id)
        if job is None:
            raise FileNotFoundError("取込ジョブが見つかりません")
        return job

    def start_edit(self, job_id: str) -> ImportedVideoJobDTO:
        job = self._require_editable_job(job_id)
        task = self._edit_tasks.get(job_id)
        if task is not None and not task.done():
            raise ValueError("この動画はすでに編集処理中です")
        self._validate_edit_selection(job)
        editing = replace(job, state="editing", progress_percent=0.0)
        self.repository.save_job(editing)
        self._edit_tasks[job_id] = asyncio.create_task(
            self.edit_selected(job_id)
        )
        return editing

    async def cancel(self, job_id: str) -> ImportedVideoJobDTO:
        self._require_job(job_id)
        tasks = [
            task
            for task in (self._tasks.get(job_id), self._edit_tasks.get(job_id))
            if task is not None and not task.done()
        ]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        latest = self._require_job(job_id)
        state = (
            "completed"
            if latest.has_output
            else "ready"
            if latest.candidates
            else "cancelled"
        )
        cancelled = replace(latest, state=state, error="処理を中止しました。")
        self.repository.save_job(cancelled)
        return cancelled

    async def shutdown(self) -> None:
        """終了時に取込処理を停止し、保存済みの再開点を保つ。"""
        active_job_ids = {
            job_id
            for tasks in (self._tasks, self._edit_tasks)
            for job_id, task in tasks.items()
            if not task.done()
        }
        active = [
            task
            for job_id in active_job_ids
            for task in (self._tasks.get(job_id), self._edit_tasks.get(job_id))
            if task is not None and not task.done()
        ]
        for task in active:
            task.cancel()
        if active:
            await asyncio.gather(*active, return_exceptions=True)
        for job_id in active_job_ids:
            job = self.repository.get_job(job_id)
            if job is None or job.state == "completed":
                continue
            if job.state in {"ready", "queued"}:
                continue
            self.repository.save_job(
                replace(
                    job,
                    state="ready" if job.candidates else "queued",
                    error="アプリ終了時に処理を中断しました。必要に応じて再開してください。",
                )
            )
        await self.resume_pending()

    def get_job(self, job_id: str) -> ImportedVideoJobDTO | None:
        return self.repository.get_job(job_id)

    def list_jobs(self) -> list[ImportedVideoJobDTO]:
        return self.repository.list_jobs()

    def asset_path(self, job_id: str, asset: str) -> Path | None:
        return self.repository.asset_path(job_id, asset)

    def get_candidate_subtitle(
        self, job_id: str, candidate_id: str
    ) -> SubtitleDataDTO:
        job = self._require_editable_job(job_id)
        candidate = self._require_candidate(job, candidate_id)
        content = self.repository.read_asset_text(
            job_id, f"candidate:{candidate_id}:subtitle.srt"
        )
        blocks = self.subtitle_converter.from_srt(content or "")
        return SubtitleDataDTO(
            blocks=blocks, video_duration=candidate.duration_seconds
        )

    def update_candidate_subtitle(
        self,
        job_id: str,
        candidate_id: str,
        subtitle_data: SubtitleDataDTO,
    ) -> SubtitleDataDTO:
        job = self._require_editable_job(job_id)
        candidate = self._require_candidate(job, candidate_id)
        duration = candidate.duration_seconds
        normalized: list[SubtitleBlockDTO] = []
        for block in subtitle_data.blocks:
            if (
                not math.isfinite(block.start_time)
                or not math.isfinite(block.end_time)
                or block.start_time < 0
                or block.end_time <= block.start_time
                or block.end_time > duration
            ):
                raise ValueError(
                    "字幕の時間は候補動画の範囲内で指定してください"
                )
            normalized.append(
                SubtitleBlockDTO(
                    index=0,
                    start_time=block.start_time,
                    end_time=block.end_time,
                    text=block.text,
                )
            )
        normalized.sort(key=lambda block: block.start_time)
        normalized = [
            replace(block, index=index)
            for index, block in enumerate(normalized, start=1)
        ]
        updated_candidate = replace(candidate, has_subtitle=bool(normalized))
        updated_job = replace(
            job,
            candidates=tuple(
                updated_candidate if item.id == candidate_id else item
                for item in job.candidates
            ),
        )
        srt = (
            self.subtitle_converter.to_srt(normalized) if normalized else None
        )
        self.repository.save_candidate_subtitle(
            updated_job, updated_candidate, srt
        )
        return SubtitleDataDTO(blocks=normalized, video_duration=duration)

    def set_selection(
        self, job_id: str, selected_ids: list[str]
    ) -> ImportedVideoJobDTO:
        job = self._require_editable_job(job_id)
        selected = set(selected_ids)
        known = {
            candidate.id
            for candidate in job.candidates
            if candidate.clip_ready
        }
        if selected - known:
            raise ValueError("選択したバトル候補が見つかりません")
        updated = replace(
            job,
            candidates=tuple(
                replace(candidate, selected=candidate.id in selected)
                for candidate in job.candidates
            ),
        )
        self.repository.save_job(updated)
        return updated

    def update_candidate(
        self,
        job_id: str,
        candidate_id: str,
        metadata_patch: dict[str, object] | None,
        title: str | None,
        description: str | None,
    ) -> ImportedVideoJobDTO:
        job = self._require_editable_job(job_id)
        candidates: list[ImportedBattleDTO] = []
        found = False
        for candidate in job.candidates:
            if candidate.id != candidate_id:
                candidates.append(candidate)
                continue
            found = True
            metadata = candidate.metadata
            if metadata_patch is not None:
                current = MetadataParser.from_dict(metadata)
                if current.result is None and any(
                    field.key in metadata_patch
                    for field in BATTLE_METADATA_FIELD_DEFINITIONS
                ):
                    message = "リザルト未取得のため、マッチ・ルール・ステージ・キル・デス・スペシャルを入力してください"
                    required = (
                        field
                        for field in BATTLE_METADATA_FIELD_DEFINITIONS
                        if field.required_for_result
                    )
                    if any(
                        parse_metadata_field_update(
                            field, metadata_patch.get(field.key)
                        )
                        is MISSING
                        for field in required
                    ):
                        raise ValueError(message)
                    try:
                        current = replace(
                            current,
                            result=BattleResult.from_dict(metadata_patch),
                        )
                    except (
                        KeyError,
                        ValueError,
                        TypeError,
                        ValidationError,
                    ) as exc:
                        raise ValueError(message) from exc
                updated = MetadataParser.parse_metadata_updates(
                    current, metadata_patch
                )
                metadata = recording_metadata_to_dict(updated)
            changed = replace(
                candidate,
                metadata=metadata,
                title=title if title is not None else candidate.title,
                description=(
                    description
                    if description is not None
                    else candidate.description
                ),
            )
            candidates.append(changed)
            self.repository.save_candidate_metadata(job_id, changed)
            self._write_text_asset(
                job_id, f"candidate:{candidate_id}:title.txt", changed.title
            )
            self._write_text_asset(
                job_id,
                f"candidate:{candidate_id}:description.txt",
                changed.description,
            )
        if not found:
            raise FileNotFoundError("バトル候補が見つかりません")
        updated_job = replace(job, candidates=tuple(candidates))
        self.repository.save_job(updated_job)
        return updated_job

    def update_job_text(
        self, job_id: str, title: str, description: str
    ) -> ImportedVideoJobDTO:
        job = self._require_editable_job(job_id)
        updated = replace(job, title=title, description=description)
        self.repository.save_job(updated)
        return updated

    def update_source_time(
        self, job_id: str, started_at: str
    ) -> ImportedVideoJobDTO:
        job = self._require_editable_job(job_id)
        try:
            started = datetime.fromisoformat(started_at)
        except ValueError as exc:
            raise ValueError("元動画の開始日時を指定してください") from exc
        candidates = tuple(
            replace(
                c,
                metadata={
                    **c.metadata,
                    "started_at": (
                        started + timedelta(seconds=c.start_seconds)
                    ).isoformat(),
                },
            )
            for c in job.candidates
        )
        for candidate in candidates:
            self.repository.save_candidate_metadata(job_id, candidate)
        updated = replace(
            job,
            candidates=candidates,
            source_started_at=started.isoformat(),
            source_started_at_inferred=False,
        )
        self.repository.save_job(updated)
        return updated

    def update_output_text(
        self, job_id: str, output_id: str, title: str, description: str
    ) -> ImportedVideoJobDTO:
        job = self._require_editable_job(job_id)
        if not any(output.id == output_id for output in job.outputs):
            raise FileNotFoundError("編集結果が見つかりません")
        self.repository.write_asset(
            job_id, f"output:{output_id}:title.txt", title
        )
        self.repository.write_asset(
            job_id, f"output:{output_id}:description.txt", description
        )
        outputs = tuple(
            replace(output, title=title, description=description)
            if output.id == output_id
            else output
            for output in job.outputs
        )
        updated = replace(
            job,
            outputs=outputs,
            title=title if job.output_id == output_id else job.title,
            description=description
            if job.output_id == output_id
            else job.description,
        )
        self.repository.save_job(updated)
        return updated

    @staticmethod
    def _validate_edit_selection(job: ImportedVideoJobDTO) -> None:
        selected = [
            candidate for candidate in job.candidates if candidate.selected
        ]
        if not selected or any(
            not candidate.clip_ready for candidate in selected
        ):
            raise ValueError("保存済みのバトルを1つ以上選択してください")
        if any(
            MetadataParser.from_dict(candidate.metadata).started_at is None
            for candidate in selected
        ):
            raise ValueError(
                "グループ分けのため元動画の開始日時を入力してください"
            )

    async def edit_selected(self, job_id: str) -> ImportedVideoJobDTO:
        job = self._require_job(job_id)
        if job.state not in {"ready", "completed", "editing"}:
            raise ValueError("解析が完了したバトル候補を選んでください")
        self._validate_edit_selection(job)
        selected = sorted(
            (c for c in job.candidates if c.selected),
            key=lambda c: c.start_seconds,
        )
        assets = [
            VideoAsset(
                video=self._candidate_asset(job_id, c.id, "video.mp4"),
                subtitle=self.repository.asset_path(
                    job_id, f"candidate:{c.id}:subtitle.srt"
                ),
                thumbnail=self.repository.asset_path(
                    job_id, f"candidate:{c.id}:result-full.png"
                ),
                metadata=MetadataParser.from_dict(c.metadata),
            )
            for c in selected
        ]
        groups = VideoGroupingService(self.logger).group_by_timeslot(assets)
        job = replace(job, state="editing", error=None)
        self.repository.save_job(job)
        outputs = list(job.outputs)
        prior_output_count = len(outputs)
        staging: Path | None = None
        try:
            for (day, time_slot, _match, _rule), group in groups.items():
                staging = self.repository.create_work_directory(
                    job_id, "output"
                )
                await self.video_editor.merge(
                    [a.video for a in group], staging / "video.mp4"
                )
                group_candidates = [
                    c
                    for c in selected
                    if any(
                        a.video
                        == self._candidate_asset(job_id, c.id, "video.mp4")
                        for a in group
                    )
                ]
                if self.renderer is None:
                    raise RuntimeError(
                        "持込動画の編集処理が設定されていません"
                    )
                rendered = await self.renderer.render(
                    staging / "video.mp4", group, day, time_slot
                )
                for name, content in (
                    ("title.txt", rendered.title),
                    ("description.txt", rendered.description),
                    ("thumbnail.png", rendered.thumbnail),
                    ("subtitle.srt", rendered.subtitle),
                ):
                    if content is not None:
                        self.repository.write_staging_file(
                            job_id, staging, name, content
                        )
                metadata = {
                    "source_name": job.source_name,
                    "battles": [
                        {
                            "candidate_id": c.id,
                            "source_spans": c.segments,
                            "metadata": c.metadata,
                        }
                        for c in group_candidates
                    ],
                }
                self.repository.write_staging_file(
                    job_id,
                    staging,
                    "metadata.json",
                    json.dumps(metadata, ensure_ascii=False, indent=2),
                )
                info = {
                    "created_at": datetime.now().astimezone().isoformat(),
                    "title": rendered.title,
                    "description": rendered.description,
                    "has_thumbnail": rendered.thumbnail is not None,
                    "has_subtitle": bool(rendered.subtitle),
                    "candidate_ids": [c.id for c in group_candidates],
                }
                output_id = self.repository.commit_output(
                    job_id, staging, info
                )
                staging = None
                outputs.append(
                    ImportedVideoOutputDTO(
                        id=output_id,
                        title=rendered.title,
                        description=rendered.description,
                        has_thumbnail=rendered.thumbnail is not None,
                        has_subtitle=bool(rendered.subtitle),
                        candidate_ids=tuple(c.id for c in group_candidates),
                    )
                )
                job = replace(
                    job,
                    outputs=tuple(outputs),
                    progress_percent=(len(outputs) - prior_output_count)
                    / len(groups)
                    * 100,
                )
                self.repository.save_job(job)
            first = outputs[-1]
            job = replace(
                job,
                state="completed",
                progress_percent=100.0,
                has_output=True,
                output_id=first.id,
                title=first.title,
                description=first.description,
                has_thumbnail=first.has_thumbnail,
                has_subtitle=first.has_subtitle,
                outputs=tuple(outputs),
                error=None,
            )
            self.repository.save_job(job)
            return job
        except BaseException as exc:
            latest = self._require_job(job_id)
            self.repository.save_job(
                replace(
                    latest,
                    state="ready",
                    error="処理を中止しました。"
                    if isinstance(exc, asyncio.CancelledError)
                    else f"編集に失敗しました: {exc}",
                )
            )
            raise
        finally:
            if staging is not None:
                self.repository.remove_work_directory(staging)

    async def _scan_job(self, job_id: str) -> None:
        job = self._require_job(job_id)
        job = replace(job, state="scanning", progress_percent=0, error=None)
        self.repository.save_job(job)
        source = self.repository.source_path(job_id)
        staging: Path | None = None
        weapon_detection: WeaponDetectionService | None = None
        try:
            info = await self.probe.inspect_imported_video(source)
            try:
                embedded_subtitle = await self.video_editor.get_subtitle(
                    source
                )
            except Exception:
                # 埋め込み字幕は任意。字幕読み取り失敗で動画解析を止めない。
                embedded_subtitle = None
            job = replace(
                job,
                duration_seconds=info.duration_seconds,
                has_audio=info.has_audio,
            )
            if (
                not math.isfinite(info.duration_seconds)
                or info.duration_seconds <= 0
            ):
                raise ValueError(
                    "動画の長さを確認できません。動画ファイルを確認してください。"
                )
            self.repository.save_job(job)

            previous_rate = None
            previous_rate_evidence: tuple[float, Frame] | None = None
            previous_match_evidence: tuple[float, Frame] | None = None
            active = False
            segment_start: float | None = None
            segments: list[tuple[float, float]] = []
            post_finish = False
            loading_paused = False
            result_seen = False
            judgement: Judgement | None = None
            result: BattleResult | None = None
            result_frame: Frame | None = None
            evidence: dict[str, tuple[float, Frame]] = {}
            recognizer: _ImportedVideoWeaponRecognizer | None = None
            rate = None
            weapon_clock: _VideoTimelineClock | None = None
            weapon_context: RecordingContext | None = None
            candidates = list(job.candidates)
            last_seconds = 0.0
            last_frame: Frame | None = None
            last_persist = asyncio.get_running_loop().time()
            incomplete_reason: str | None = None
            frame_count = 0

            def persist_progress(seconds: float) -> None:
                nonlocal job, last_persist
                now = asyncio.get_running_loop().time()
                if now - last_persist < 2.0:
                    return
                job = replace(
                    job,
                    progress_percent=min(
                        99.0, seconds / info.duration_seconds * 100
                    ),
                    candidates=tuple(candidates),
                    error=incomplete_reason,
                )
                self.repository.save_job(job)
                last_persist = now

            async for seconds, frame in self.frame_reader.frames(
                source, _SCAN_INTERVAL_SECONDS
            ):
                last_seconds = seconds
                last_frame = frame
                frame_count += 1
                # 判定待ちや画面遷移中も、長尺動画の進行位置を保存する。
                persist_progress(seconds)
                if not active:
                    if await self.analyzer.detect_match_select(frame):
                        detected_match = (
                            await self.analyzer.extract_match_select(
                                frame, GameMode.BATTLE
                            )
                        )
                        if detected_match is not None:
                            previous_match_evidence = (seconds, frame.copy())
                            previous_rate = (
                                await self.analyzer.extract_rate_for_match(
                                    frame, GameMode.BATTLE, detected_match
                                )
                            )
                            previous_rate_evidence = (
                                (seconds, frame.copy())
                                if previous_rate is not None
                                else None
                            )
                    if await self.analyzer.detect_session_start(
                        frame, GameMode.BATTLE
                    ):
                        active = True
                        segment_start = seconds
                        weapon_clock = _VideoTimelineClock()
                        weapon_clock.seconds = seconds
                        weapon_context = RecordingContext(
                            metadata=RecordingMetadata(
                                game_mode=GameMode.BATTLE
                            ),
                            battle_started_at=max(seconds, 0.001),
                        )
                        recognizer = _ImportedVideoWeaponRecognizer(
                            self.weapon_recognition_factory.create()
                        )
                        recognizer.seconds = seconds
                        recognizer.remember_frame(frame, seconds)
                        evidence = (
                            {"rate": previous_rate_evidence}
                            if previous_rate_evidence is not None
                            else {}
                        )
                        if previous_match_evidence is not None:
                            evidence["match_select"] = previous_match_evidence
                        weapon_detection = WeaponDetectionService(
                            recognizer=recognizer,
                            logger=self.logger,
                            event_bus=_ImportedVideoEventSink(),
                            detection_window_seconds=DETECTION_WINDOW_SECONDS,
                            clock=weapon_clock,
                        )
                        weapon_context = await weapon_detection.process(
                            frame=frame, context=weapon_context
                        )
                        weapon_context = (
                            await weapon_detection.wait_for_pending(
                                context=weapon_context
                            )
                        )
                        rate = previous_rate
                        segments = []
                        post_finish = False
                        loading_paused = False
                        result_seen = False
                        judgement = None
                        result = None
                        result_frame = None
                    else:
                        continue
                else:
                    if (
                        weapon_detection is not None
                        and weapon_clock is not None
                        and weapon_context is not None
                    ):
                        weapon_clock.seconds = seconds
                        if recognizer is not None:
                            recognizer.seconds = seconds
                            recognizer.remember_frame(frame, seconds)
                        weapon_context = await weapon_detection.process(
                            frame=frame, context=weapon_context
                        )
                        weapon_context = (
                            await weapon_detection.wait_for_pending(
                                context=weapon_context
                            )
                        )

                if active and not post_finish:
                    if await self.analyzer.detect_session_abort(
                        frame, GameMode.BATTLE
                    ):
                        if weapon_detection is not None:
                            await weapon_detection.close()
                        weapon_detection = None
                        weapon_context = None
                        weapon_clock = None
                        active = False
                        segment_start = None
                        segments = []
                        incomplete_reason = (
                            "途中終了した対戦を候補から除外しました。"
                        )
                    elif await self.analyzer.detect_communication_error(
                        frame, GameMode.BATTLE
                    ):
                        if weapon_detection is not None:
                            await weapon_detection.close()
                        weapon_detection = None
                        weapon_context = None
                        weapon_clock = None
                        active = False
                        segment_start = None
                        segments = []
                        incomplete_reason = (
                            "通信エラーで終了した対戦を候補から除外しました。"
                        )
                    elif await self.analyzer.detect_session_finish(
                        frame, GameMode.BATTLE
                    ):
                        self._close_segment(segments, segment_start, seconds)
                        segment_start = None
                        post_finish = True
                elif active:
                    if loading_paused:
                        if await self.analyzer.detect_loading_end(frame):
                            loading_paused = False
                            segment_start = seconds
                        continue
                    if (
                        judgement is None
                        and await self.analyzer.detect_session_judgement(
                            frame, GameMode.BATTLE
                        )
                    ):
                        evidence["judgement"] = (seconds, frame.copy())
                        judgement = (
                            await self.analyzer.extract_session_judgement(
                                frame, GameMode.BATTLE
                            )
                        )
                        segment_start = seconds
                        continue
                    if await self.analyzer.detect_loading(frame):
                        self._close_segment(segments, segment_start, seconds)
                        segment_start = None
                        loading_paused = True
                        continue
                    still_result = await self.analyzer.detect_session_result(
                        frame, GameMode.BATTLE
                    )
                    if still_result:
                        result_seen = True
                        if result_frame is None:
                            result_frame = frame
                            evidence["result"] = (seconds, frame.copy())
                    elif result_seen:
                        if result_frame is not None:
                            extracted = (
                                await self.analyzer.extract_session_result(
                                    result_frame, GameMode.BATTLE
                                )
                            )
                            if isinstance(extracted, BattleResult):
                                result = extracted
                        self._close_segment(segments, segment_start, seconds)
                        metadata = await self._finish_weapon_detection(
                            weapon_detection,
                            weapon_context,
                            weapon_clock,
                            frame,
                            seconds,
                            rate,
                            judgement,
                            result,
                        )
                        weapon_detection = None
                        weapon_context = None
                        weapon_clock = None
                        if segments:
                            metadata = self._candidate_metadata_time(
                                job, metadata, tuple(segments)
                            )
                            if (
                                recognizer is not None
                                and recognizer.evidence_frame is not None
                            ):
                                evidence["weapons"] = (
                                    recognizer.evidence_seconds,
                                    recognizer.evidence_frame,
                                )
                            (
                                staging,
                                has_thumbnail,
                                has_subtitle,
                            ) = await self._save_candidate(
                                job_id,
                                metadata,
                                tuple(segments),
                                embedded_subtitle,
                                len(candidates) + 1,
                                evidence,
                            )
                            candidate = self._candidate_from_staging(
                                staging,
                                metadata,
                                tuple(segments),
                                len(candidates) + 1,
                                has_subtitle,
                                has_thumbnail,
                                evidence,
                            )
                            self.repository.commit_candidate(
                                job_id, candidate, candidate.id, staging
                            )
                            staging = None
                            candidates.append(candidate)
                            job = replace(job, candidates=tuple(candidates))
                            self.repository.save_job(job)
                        else:
                            incomplete_reason = "対戦の映像区間を確定できず候補から除外しました。"
                        active = False
                        segment_start = None
                        segments = []

            if frame_count == 0:
                raise ValueError("動画からフレームを読み込めませんでした。")
            if last_seconds < info.duration_seconds - max(
                3.0, info.duration_seconds * 0.03
            ):
                raise ValueError(
                    "動画の最後まで読み込めませんでした。ファイルが破損している可能性があります。"
                )
            if (
                active
                and post_finish
                and result_seen
                and last_frame is not None
            ):
                if result is None and result_frame is not None:
                    extracted = await self.analyzer.extract_session_result(
                        result_frame, GameMode.BATTLE
                    )
                    if isinstance(extracted, BattleResult):
                        result = extracted
                self._close_segment(
                    segments, segment_start, info.duration_seconds
                )
                metadata = await self._finish_weapon_detection(
                    weapon_detection,
                    weapon_context,
                    weapon_clock,
                    last_frame,
                    info.duration_seconds,
                    rate,
                    judgement,
                    result,
                )
                weapon_detection = None
                weapon_context = None
                weapon_clock = None
                if segments:
                    metadata = self._candidate_metadata_time(
                        job, metadata, tuple(segments)
                    )
                    if (
                        recognizer is not None
                        and recognizer.evidence_frame is not None
                    ):
                        evidence["weapons"] = (
                            recognizer.evidence_seconds,
                            recognizer.evidence_frame,
                        )
                    (
                        staging,
                        has_thumbnail,
                        has_subtitle,
                    ) = await self._save_candidate(
                        job_id,
                        metadata,
                        tuple(segments),
                        embedded_subtitle,
                        len(candidates) + 1,
                        evidence,
                    )
                    candidate = self._candidate_from_staging(
                        staging,
                        metadata,
                        tuple(segments),
                        len(candidates) + 1,
                        has_subtitle,
                        has_thumbnail,
                        evidence,
                    )
                    self.repository.commit_candidate(
                        job_id, candidate, candidate.id, staging
                    )
                    staging = None
                    candidates.append(candidate)
                    job = replace(job, candidates=tuple(candidates))
                    self.repository.save_job(job)
                else:
                    incomplete_reason = (
                        "対戦の映像区間を確定できず候補から除外しました。"
                    )
            elif active:
                incomplete_reason = "動画の末尾までに対戦結果を確認できず、最後の対戦は未完了として除外しました。"
                if weapon_detection is not None:
                    await weapon_detection.close()
                weapon_detection = None
            final_state = "ready" if candidates else "failed"
            job = replace(
                job,
                state=final_state,
                progress_percent=100.0,
                candidates=tuple(candidates),
                error=(
                    incomplete_reason
                    or (
                        None
                        if candidates
                        else "バトルを検出できませんでした。ゲーム画面が映った動画を選んでください。"
                    )
                ),
            )
            self.repository.save_job(job)
        except asyncio.CancelledError:
            if weapon_detection is not None:
                await weapon_detection.close()
            if staging is not None:
                self.repository.remove_candidate_staging_directory(staging)
            latest = self._require_job(job_id)
            self.repository.save_job(
                replace(
                    latest,
                    state="ready" if latest.candidates else "cancelled",
                    error="解析を中止しました。",
                )
            )
            raise
        except Exception as exc:
            if weapon_detection is not None:
                await weapon_detection.close()
            if staging is not None:
                self.repository.remove_candidate_staging_directory(staging)
            latest = self._require_job(job_id)
            state = "ready" if latest.candidates else "failed"
            self.repository.save_job(
                replace(latest, state=state, error=str(exc))
            )

    async def _finish_weapon_detection(
        self,
        service: WeaponDetectionService | None,
        context: RecordingContext | None,
        clock: _VideoTimelineClock | None,
        frame: Frame,
        seconds: float,
        rate: RateBase | None,
        judgement: Judgement | None,
        result: BattleResult | None,
    ) -> RecordingMetadata:
        metadata = RecordingMetadata(game_mode=GameMode.BATTLE)
        if service is not None and context is not None and clock is not None:
            clock.seconds = seconds
            finished = await service.finalize_for_finish(
                frame=frame, context=context
            )
            metadata = finished.metadata
            await service.close()
        return replace(
            metadata,
            game_mode=GameMode.BATTLE,
            started_at=None,
            rate=rate,
            judgement=judgement,
            result=result,
            allies=metadata.allies or _UNKNOWN_WEAPONS,
            enemies=metadata.enemies or _UNKNOWN_WEAPONS,
        )

    async def _save_candidate(
        self,
        job_id: str,
        metadata: RecordingMetadata,
        segments: tuple[tuple[float, float], ...],
        source_subtitle: str | None,
        ordinal: int,
        evidence: dict[str, tuple[float, Frame]] | None = None,
    ) -> tuple[Path, bool, bool]:
        candidate_id = str(uuid4())
        staging = self.repository.candidate_staging_directory(
            job_id, candidate_id
        )
        try:
            for kind, (_, frame) in (evidence or {}).items():
                self.repository.save_evidence_frame(
                    job_id, staging, kind, frame
                )
                if kind == "result":
                    self.repository.save_evidence_frame(
                        job_id, staging, "result-full", frame
                    )
            source = self.repository.source_path(job_id)
            segment_paths: list[Path] = []
            for index, (start, end) in enumerate(segments):
                segment_path = staging / f"part-{index}.mp4"
                await self.video_editor.cut_segment(
                    source, start, end, segment_path
                )
                segment_paths.append(segment_path)
            if len(segment_paths) == 1:
                self.repository.move_staging_file(
                    job_id, staging, segment_paths[0].name, "video.mp4"
                )
            else:
                await self.video_editor.merge(
                    segment_paths, staging / "video.mp4"
                )
            for path in segment_paths:
                self.repository.remove_staging_file(job_id, staging, path.name)
            metadata_dict = recording_metadata_to_dict(metadata)
            self.repository.write_staging_file(
                job_id,
                staging,
                "metadata.json",
                json.dumps(metadata_dict, ensure_ascii=False, indent=2),
            )
            title, description = self._describe_candidate(metadata, ordinal)
            self.repository.write_staging_file(
                job_id, staging, "title.txt", title
            )
            self.repository.write_staging_file(
                job_id, staging, "description.txt", description
            )
            thumbnail = await self.frame_preview.extract_frame(
                staging / "video.mp4", 0
            )
            if thumbnail is not None:
                self.repository.write_staging_file(
                    job_id, staging, "thumbnail.png", thumbnail
                )
            try:
                subtitle = self._slice_subtitle(source_subtitle, segments)
            except ValueError:
                subtitle = None
            if subtitle:
                self.repository.write_staging_file(
                    job_id, staging, "subtitle.srt", subtitle
                )
            return staging, thumbnail is not None, bool(subtitle)
        except BaseException:
            self.repository.remove_candidate_staging_directory(staging)
            raise

    def _candidate_from_staging(
        self,
        staging: Path,
        metadata: RecordingMetadata,
        segments: tuple[tuple[float, float], ...],
        ordinal: int,
        has_subtitle: bool,
        has_thumbnail: bool,
        evidence: dict[str, tuple[float, Frame]] | None = None,
    ) -> ImportedBattleDTO:
        metadata_dict: dict[str, object] = dict(
            recording_metadata_to_dict(metadata)
        )
        title, description = self._describe_candidate(metadata, ordinal)
        duration = sum(end - start for start, end in segments)
        candidate_id = staging.name
        return ImportedBattleDTO(
            id=candidate_id,
            start_seconds=segments[0][0],
            end_seconds=segments[-1][1],
            segments=segments,
            selected=True,
            metadata=metadata_dict,
            title=title,
            description=description,
            clip_ready=True,
            duration_seconds=duration,
            has_thumbnail=has_thumbnail,
            has_subtitle=has_subtitle,
            evidence_assets={
                kind: f"candidate/{candidate_id}/{kind}.png"
                for kind in (evidence or {})
            },
            evidence_seconds={
                kind: seconds
                for kind, (seconds, _) in (evidence or {}).items()
            },
        )

    @staticmethod
    def _candidate_metadata_time(
        job: ImportedVideoJobDTO,
        metadata: RecordingMetadata,
        segments: tuple[tuple[float, float], ...],
    ) -> RecordingMetadata:
        if job.source_started_at is None:
            return metadata
        return replace(
            metadata,
            started_at=datetime.fromisoformat(job.source_started_at)
            + timedelta(seconds=segments[0][0]),
        )

    @staticmethod
    def _describe_candidate(
        metadata: RecordingMetadata, ordinal: int
    ) -> tuple[str, str]:
        # 元動画に対戦日時が記録されていない場合、解析時刻で補わない。
        result = metadata.result
        judgement = (
            metadata.judgement.value if metadata.judgement else "結果不明"
        )
        stage = (
            result.stage.value
            if isinstance(result, BattleResult) and result.stage
            else "ステージ不明"
        )
        rule = (
            result.rule.value
            if isinstance(result, BattleResult) and result.rule
            else "ルール不明"
        )
        title = f"対戦 {ordinal}: {judgement} / {stage}"
        description = (
            f"{rule}・{stage}。元動画内 {metadata.game_mode.value} 対戦。"
        )
        return title, description

    def _slice_subtitle(
        self,
        source_subtitle: str | None,
        segments: tuple[tuple[float, float], ...],
    ) -> str | None:
        if not source_subtitle:
            return None
        blocks = self.subtitle_converter.from_srt(source_subtitle)
        result = []
        output_offset = 0.0
        index = 1
        for start, end in segments:
            for block in blocks:
                clipped_start = max(start, block.start_time)
                clipped_end = min(end, block.end_time)
                if clipped_end <= clipped_start:
                    continue
                result.append(
                    replace(
                        block,
                        index=index,
                        start_time=output_offset + clipped_start - start,
                        end_time=output_offset + clipped_end - start,
                    )
                )
                index += 1
            output_offset += end - start
        return self.subtitle_converter.to_srt(result) if result else None

    def _combine_subtitles(
        self, job_id: str, candidates: list[ImportedBattleDTO]
    ) -> str | None:
        output = []
        offset = 0.0
        index = 1
        for candidate in candidates:
            text = self.repository.read_asset_text(
                job_id, f"candidate:{candidate.id}:subtitle.srt"
            )
            if text is None:
                offset += candidate.duration_seconds
                continue
            for block in self.subtitle_converter.from_srt(text):
                output.append(
                    replace(
                        block,
                        index=index,
                        start_time=block.start_time + offset,
                        end_time=block.end_time + offset,
                    )
                )
                index += 1
            offset += candidate.duration_seconds
        return self.subtitle_converter.to_srt(output) if output else None

    def _candidate_asset(
        self, job_id: str, candidate_id: str, name: str
    ) -> Path:
        path = self.repository.asset_path(
            job_id, f"candidate:{candidate_id}:{name}"
        )
        if path is None:
            raise FileNotFoundError("保存済み候補の動画が見つかりません")
        return path

    def _write_text_asset(
        self, job_id: str, asset: str, value: str | None
    ) -> None:
        if value is not None:
            self.repository.write_asset(job_id, asset, value)

    def _require_job(self, job_id: str) -> ImportedVideoJobDTO:
        job = self.repository.get_job(job_id)
        if job is None:
            raise FileNotFoundError("取込ジョブが見つかりません")
        return job

    def _require_editable_job(self, job_id: str) -> ImportedVideoJobDTO:
        job = self._require_job(job_id)
        if job.state not in {"ready", "completed"}:
            raise ValueError("解析が完了したバトル候補を選んでください")
        return job

    @staticmethod
    def _require_candidate(
        job: ImportedVideoJobDTO, candidate_id: str
    ) -> ImportedBattleDTO:
        for candidate in job.candidates:
            if candidate.id == candidate_id:
                if not candidate.clip_ready:
                    raise ValueError("保存済みの候補動画がありません")
                if (
                    not math.isfinite(candidate.duration_seconds)
                    or candidate.duration_seconds <= 0
                ):
                    raise ValueError("候補動画の長さを確認できません")
                return candidate
        raise FileNotFoundError("バトル候補が見つかりません")

    @staticmethod
    def _close_segment(
        segments: list[tuple[float, float]], start: float | None, end: float
    ) -> None:
        if start is not None and end > start:
            segments.append((start, end))
