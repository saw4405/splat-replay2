"""持込動画の解析再開とEOF完了候補のlogic。"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import replace
from pathlib import Path
from datetime import date, time
import json
from typing import Callable, cast
from uuid import uuid4

import numpy as np
import pytest

from splat_replay.application.dto.imported_video import (
    ImportedBattleDTO,
    ImportedVideoInfo,
)
from splat_replay.application.services.common.subtitle_converter import (
    SubtitleConverter,
)
from splat_replay.application.dto.subtitle import (
    SubtitleBlockDTO,
    SubtitleDataDTO,
)
from splat_replay.application.services.imported_video_service import (
    ImportedVideoService,
)
from splat_replay.application.interfaces import (
    FramePreviewPort,
    VideoEditorPort,
)
from splat_replay.application.interfaces import (
    WeaponCandidateScore,
    WeaponDisplayDetectionResult,
    WeaponRecognitionResult,
    WeaponSlotResult,
)
from splat_replay.domain.models import (
    BattleResult,
    GameMode,
    Match,
    RateBase,
    XP,
    VideoAsset,
    Judgement,
)
from splat_replay.application.interfaces.imported_video import (
    ImportedVideoRenderResult,
)
from splat_replay.domain.services import FrameAnalyzer
from splat_replay.infrastructure.repositories.imported_video_repo import (
    FileImportedVideoRepository,
)


async def _source_chunks() -> AsyncIterator[bytes]:
    yield b"untouched source"


class _Reader:
    def __init__(self) -> None:
        self.read_count = 0

    def frames(
        self, path: Path, sample_interval_seconds: float
    ) -> AsyncIterator[tuple[float, np.ndarray]]:
        _ = path, sample_interval_seconds

        async def iterate() -> AsyncIterator[tuple[float, np.ndarray]]:
            self.read_count += 1
            for seconds, marker in (
                (0.0, 0),
                (1.0, 1),
                (4.0, 3),
                (5.0, 4),
                (6.0, 5),
                (8.0, 6),
                (9.0, 6),
            ):
                yield seconds, np.full((2, 2, 3), marker, dtype=np.uint8)

        return iterate()


class _BlockingReader:
    def __init__(self) -> None:
        self.started = asyncio.Event()

    def frames(
        self, path: Path, sample_interval_seconds: float
    ) -> AsyncIterator[tuple[float, np.ndarray]]:
        _ = path, sample_interval_seconds

        async def iterate() -> AsyncIterator[tuple[float, np.ndarray]]:
            self.started.set()
            yield 0.0, np.zeros((2, 2, 3), dtype=np.uint8)
            await asyncio.Event().wait()

        return iterate()


class _Probe:
    async def inspect_imported_video(self, path: Path) -> ImportedVideoInfo:
        _ = path
        return ImportedVideoInfo(10.0, has_video=True, has_audio=False)


class _Analyzer:
    @staticmethod
    def _marker(frame: np.ndarray) -> int:
        return int(frame[0, 0, 0])

    async def detect_match_select(self, frame: np.ndarray) -> bool:
        return self._marker(frame) == 0

    async def extract_match_select(
        self, frame: np.ndarray, mode: GameMode
    ) -> Match | None:
        _ = frame, mode
        return None

    async def extract_rate_for_match(
        self, frame: np.ndarray, mode: GameMode, match: object
    ) -> RateBase | None:
        _ = frame, mode, match
        return None

    async def detect_session_start(
        self, frame: np.ndarray, mode: GameMode
    ) -> bool:
        _ = mode
        return self._marker(frame) == 1

    async def detect_session_abort(
        self, frame: np.ndarray, mode: GameMode
    ) -> bool:
        _ = frame, mode
        return False

    async def detect_communication_error(
        self, frame: np.ndarray, mode: GameMode
    ) -> bool:
        _ = frame, mode
        return False

    async def detect_session_finish(
        self, frame: np.ndarray, mode: GameMode
    ) -> bool:
        _ = mode
        return self._marker(frame) == 3

    async def detect_loading_end(self, frame: np.ndarray) -> bool:
        return self._marker(frame) == 5

    async def detect_session_judgement(
        self, frame: np.ndarray, mode: GameMode
    ) -> bool:
        _ = frame, mode
        return False

    async def detect_loading(self, frame: np.ndarray) -> bool:
        return self._marker(frame) == 4

    async def detect_session_result(
        self, frame: np.ndarray, mode: GameMode
    ) -> bool:
        _ = mode
        return self._marker(frame) == 6

    async def extract_session_result(
        self, frame: np.ndarray, mode: GameMode
    ) -> BattleResult:
        _ = frame, mode
        return BattleResult(None, None, None, 0, 0, 0)


class _Editor:
    async def cut_segment(
        self,
        source: Path,
        start_seconds: float,
        end_seconds: float,
        output: Path,
    ) -> Path:
        _ = source, start_seconds, end_seconds
        output.write_bytes(b"cut")
        return output

    async def merge(
        self,
        clips: list[Path],
        output: Path,
        *,
        on_progress: Callable[[float, str | None], None] | None = None,
    ) -> Path:
        _ = clips
        output.write_bytes(b"merged")
        if on_progress is not None:
            on_progress(50.0, "編集")
        return output

    async def extract_frame(
        self, path: Path, at_seconds: float
    ) -> bytes | None:
        _ = path, at_seconds
        return None

    async def get_subtitle(self, path: Path) -> str | None:
        _ = path
        return None


class _WeaponRecognizer:
    def __init__(self) -> None:
        self.recognition_calls = 0

    def request_cancel(self) -> None:
        return None

    async def detect_weapon_display(self, frame: np.ndarray) -> bool:
        _ = frame
        return True

    async def detect_weapon_display_details(
        self, frame: np.ndarray
    ) -> WeaponDisplayDetectionResult:
        _ = frame
        return WeaponDisplayDetectionResult(
            is_visible=True, should_recognize=True, score=1.0
        )

    async def recognize_weapons(
        self,
        frame: np.ndarray,
        save_predict_weapons_output: bool = True,
        target_slots: set[str] | None = None,
        previous_results: dict[str, WeaponSlotResult] | None = None,
        battle_dir_name: str | None = None,
    ) -> WeaponRecognitionResult:
        _ = frame, save_predict_weapons_output, battle_dir_name
        self.recognition_calls += 1
        names = (
            "ally_1",
            "ally_2",
            "ally_3",
            "ally_4",
            "enemy_1",
            "enemy_2",
            "enemy_3",
            "enemy_4",
        )
        results = []
        for index, slot in enumerate(names):
            if target_slots is not None and slot not in target_slots:
                if previous_results is not None and slot in previous_results:
                    results.append(previous_results[slot])
                    continue
            weapon = f"ブキ{index}"
            results.append(
                WeaponSlotResult(
                    slot=slot,
                    predicted_weapon=weapon,
                    is_unmatched=False,
                    top_candidates=(
                        WeaponCandidateScore(
                            weapon=weapon, score=0.9, threshold=0.5
                        ),
                    ),
                )
            )
        return WeaponRecognitionResult(
            allies=(
                results[0].predicted_weapon,
                results[1].predicted_weapon,
                results[2].predicted_weapon,
                results[3].predicted_weapon,
            ),
            enemies=(
                results[4].predicted_weapon,
                results[5].predicted_weapon,
                results[6].predicted_weapon,
                results[7].predicted_weapon,
            ),
            slot_results=tuple(results),
        )

    async def save_predict_weapons_output(
        self,
        frame: np.ndarray,
        slot_results: tuple[WeaponSlotResult, ...],
        battle_dir_name: str | None = None,
    ) -> str | None:
        _ = frame, slot_results, battle_dir_name
        return None


class _WeaponFactory:
    def __init__(self) -> None:
        self.recognizer = _WeaponRecognizer()
        self.create_count = 0

    def create(self) -> _WeaponRecognizer:
        self.create_count += 1
        return self.recognizer


class _Renderer:
    async def render(
        self, target: Path, group: list[VideoAsset], day: date, time_slot: time
    ) -> ImportedVideoRenderResult:
        subtitle = next(
            (
                asset.subtitle.read_text(encoding="utf-8")
                for asset in group
                if asset.subtitle
            ),
            None,
        )
        return ImportedVideoRenderResult("編集済み", "説明", None, subtitle)


class _FailSecondRenderer(_Renderer):
    def __init__(self) -> None:
        self.calls = 0

    async def render(
        self, target: Path, group: list[VideoAsset], day: date, time_slot: time
    ) -> ImportedVideoRenderResult:
        self.calls += 1
        if self.calls == 2:
            raise RuntimeError("二つ目のグループで編集失敗")
        return await super().render(target, group, day, time_slot)


class _Logger:
    def debug(self, event: str, **kw: object) -> None:
        _ = event, kw

    def info(self, event: str, **kw: object) -> None:
        _ = event, kw

    def warning(self, event: str, **kw: object) -> None:
        _ = event, kw

    def error(self, event: str, **kw: object) -> None:
        _ = event, kw

    def exception(self, event: str, **kw: object) -> None:
        _ = event, kw


@pytest.mark.asyncio
async def test_startup_requeues_without_scanning_and_eof_saves_completed_battle(
    tmp_path: Path,
) -> None:
    repository = FileImportedVideoRepository(tmp_path)
    job = await repository.create_job("playback.mp4", ".mp4", _source_chunks())
    repository.save_job(replace(job, state="scanning", progress_percent=36))
    reader = _Reader()
    weapon_factory = _WeaponFactory()
    service = ImportedVideoService(
        repository=repository,
        frame_reader=reader,
        probe=_Probe(),
        video_editor=cast(VideoEditorPort, _Editor()),
        frame_preview=cast(FramePreviewPort, _Editor()),
        analyzer=cast(FrameAnalyzer, _Analyzer()),
        subtitle_converter=SubtitleConverter(),
        weapon_recognition_factory=weapon_factory,
        logger=_Logger(),
        renderer=_Renderer(),
    )

    await service.resume_pending()
    requeued = repository.get_job(job.id)
    assert requeued is not None and requeued.state == "queued"
    assert reader.read_count == 0

    service.start_scan(job.id)
    completed = await service.wait_for_scan(job.id)
    assert completed.state == "ready"
    assert len(completed.candidates) == 1
    candidate = completed.candidates[0]
    assert candidate.selected is True and candidate.clip_ready is True
    assert candidate.segments == ((1.0, 4.0), (6.0, 10.0))
    assert candidate.end_seconds == 10.0
    assert candidate.metadata["started_at"] is None
    assert "rate" not in candidate.evidence_assets
    assert candidate.metadata["allies"] == ["ブキ0", "ブキ1", "ブキ2", "ブキ3"]
    assert candidate.metadata["enemies"] == [
        "ブキ4",
        "ブキ5",
        "ブキ6",
        "ブキ7",
    ]
    assert weapon_factory.create_count == 1
    assert weapon_factory.recognizer.recognition_calls >= 1
    assert repository.source_path(job.id).read_bytes() == b"untouched source"
    assert (
        repository.asset_path(job.id, f"candidate:{candidate.id}:video.mp4")
        is not None
    )


@pytest.mark.asyncio
async def test_create_import_returns_scanning_state_for_progress_polling(
    tmp_path: Path,
) -> None:
    service = ImportedVideoService(
        repository=FileImportedVideoRepository(tmp_path),
        frame_reader=_Reader(),
        probe=_Probe(),
        video_editor=cast(VideoEditorPort, _Editor()),
        frame_preview=cast(FramePreviewPort, _Editor()),
        analyzer=cast(FrameAnalyzer, _Analyzer()),
        subtitle_converter=SubtitleConverter(),
        weapon_recognition_factory=_WeaponFactory(),
        logger=_Logger(),
        renderer=_Renderer(),
    )

    job = await service.create_import("playback.mp4", ".mp4", _source_chunks())

    assert job.state == "scanning"
    completed = await service.wait_for_scan(job.id)
    assert completed.state == "ready"


@pytest.mark.asyncio
@pytest.mark.parametrize("shutdown", [False, True])
async def test_cancel_and_shutdown_wait_for_scan_worker(
    tmp_path: Path, shutdown: bool
) -> None:
    repository = FileImportedVideoRepository(tmp_path)
    job = await repository.create_job("playback.mp4", ".mp4", _source_chunks())
    reader = _BlockingReader()
    service = ImportedVideoService(
        repository=repository,
        frame_reader=reader,
        probe=_Probe(),
        video_editor=cast(VideoEditorPort, _Editor()),
        frame_preview=cast(FramePreviewPort, _Editor()),
        analyzer=cast(FrameAnalyzer, _Analyzer()),
        subtitle_converter=SubtitleConverter(),
        weapon_recognition_factory=_WeaponFactory(),
        logger=_Logger(),
        renderer=_Renderer(),
    )
    service.start_scan(job.id)
    await asyncio.wait_for(reader.started.wait(), timeout=2)

    if shutdown:
        await service.shutdown()
        expected_state = "queued"
    else:
        cancelled = await service.cancel(job.id)
        expected_state = "cancelled"
        assert cancelled.state == expected_state

    stored = repository.get_job(job.id)
    assert stored is not None and stored.state == expected_state
    assert all(task.done() for task in service._tasks.values())


@pytest.mark.asyncio
async def test_edit_selected_keeps_committed_output_and_removes_only_staging(
    tmp_path: Path,
) -> None:
    repository = FileImportedVideoRepository(tmp_path)
    job = await repository.create_job("playback.mp4", ".mp4", _source_chunks())
    candidate_id = str(uuid4())
    staging = repository.candidate_staging_directory(job.id, candidate_id)
    repository.write_staging_file(job.id, staging, "video.mp4", b"battle clip")
    candidate = ImportedBattleDTO(
        id=candidate_id,
        start_seconds=1.0,
        end_seconds=3.0,
        segments=((1.0, 3.0),),
        selected=True,
        metadata={
            "game_mode": GameMode.BATTLE.name,
            "started_at": "2026-10-23T22:00:00",
        },
        title="対戦 1",
        description="候補",
        clip_ready=True,
        duration_seconds=2.0,
    )
    repository.commit_candidate(job.id, candidate, candidate_id, staging)
    repository.save_job(replace(job, state="ready", candidates=(candidate,)))
    service = ImportedVideoService(
        repository=repository,
        frame_reader=_Reader(),
        probe=_Probe(),
        video_editor=cast(VideoEditorPort, _Editor()),
        frame_preview=cast(FramePreviewPort, _Editor()),
        analyzer=cast(FrameAnalyzer, _Analyzer()),
        subtitle_converter=SubtitleConverter(),
        weapon_recognition_factory=_WeaponFactory(),
        logger=_Logger(),
        renderer=_Renderer(),
    )

    completed = await service.edit_selected(job.id)

    assert completed.state == "completed"
    assert completed.output_id is not None
    output = repository.asset_path(
        job.id, f"output:{completed.output_id}:video.mp4"
    )
    assert output is not None and output.read_bytes() == b"merged"
    assert list((tmp_path / "imports" / job.id).glob(".output-*")) == []


@pytest.mark.asyncio
async def test_candidate_subtitle_edit_updates_next_output_and_preserves_committed_one(
    tmp_path: Path,
) -> None:
    repository = FileImportedVideoRepository(tmp_path)
    job = await repository.create_job("playback.mp4", ".mp4", _source_chunks())
    candidate_id = str(uuid4())
    staging = repository.candidate_staging_directory(job.id, candidate_id)
    repository.write_staging_file(job.id, staging, "video.mp4", b"battle clip")
    candidate = ImportedBattleDTO(
        id=candidate_id,
        start_seconds=1.0,
        end_seconds=3.0,
        segments=((1.0, 3.0),),
        selected=True,
        metadata={
            "game_mode": GameMode.BATTLE.name,
            "started_at": "2026-10-23T22:00:00",
        },
        clip_ready=True,
        duration_seconds=2.0,
    )
    repository.commit_candidate(job.id, candidate, candidate_id, staging)
    repository.save_job(replace(job, state="ready", candidates=(candidate,)))
    service = ImportedVideoService(
        repository=repository,
        frame_reader=_Reader(),
        probe=_Probe(),
        video_editor=cast(VideoEditorPort, _Editor()),
        frame_preview=cast(FramePreviewPort, _Editor()),
        analyzer=cast(FrameAnalyzer, _Analyzer()),
        subtitle_converter=SubtitleConverter(),
        weapon_recognition_factory=_WeaponFactory(),
        logger=_Logger(),
        renderer=_Renderer(),
    )

    saved = service.update_candidate_subtitle(
        job.id,
        candidate_id,
        SubtitleDataDTO(
            blocks=[SubtitleBlockDTO(7, 0.5, 1.5, "候補字幕")],
            video_duration=None,
        ),
    )
    assert saved.blocks == [SubtitleBlockDTO(1, 0.5, 1.5, "候補字幕")]
    current = repository.get_job(job.id)
    assert current is not None and current.candidates[0].has_subtitle
    candidate_srt = repository.asset_path(
        job.id, f"candidate:{candidate_id}:subtitle.srt"
    )
    assert candidate_srt is not None
    assert "候補字幕" in candidate_srt.read_text(encoding="utf-8")

    first_output = await service.edit_selected(job.id)
    assert first_output.output_id is not None
    first_srt = repository.asset_path(
        job.id, f"output:{first_output.output_id}:subtitle.srt"
    )
    assert first_srt is not None
    first_output_subtitle = first_srt.read_text(encoding="utf-8")
    first_video = repository.asset_path(
        job.id, f"output:{first_output.output_id}:video.mp4"
    )
    assert first_video is not None
    first_video_bytes = first_video.read_bytes()

    with pytest.raises(ValueError, match="候補動画の範囲内"):
        service.update_candidate_subtitle(
            job.id,
            candidate_id,
            SubtitleDataDTO(blocks=[SubtitleBlockDTO(1, 1.5, 2.1, "範囲外")]),
        )

    service.update_candidate_subtitle(
        job.id, candidate_id, SubtitleDataDTO(blocks=[])
    )
    current = repository.get_job(job.id)
    assert current is not None and not current.candidates[0].has_subtitle
    assert (
        repository.asset_path(job.id, f"candidate:{candidate_id}:subtitle.srt")
        is None
    )
    assert first_srt.read_text(encoding="utf-8") == first_output_subtitle
    assert first_video.read_bytes() == first_video_bytes

    service.update_candidate_subtitle(
        job.id,
        candidate_id,
        SubtitleDataDTO(
            blocks=[SubtitleBlockDTO(1, 0.25, 1.25, "更新後の字幕")]
        ),
    )
    second_output = await service.edit_selected(job.id)
    assert second_output.output_id is not None
    second_srt = repository.asset_path(
        job.id, f"output:{second_output.output_id}:subtitle.srt"
    )
    assert second_srt is not None
    assert "更新後の字幕" in second_srt.read_text(encoding="utf-8")
    assert first_srt.read_text(encoding="utf-8") == first_output_subtitle


class _EvidenceAnalyzer(_Analyzer):
    async def detect_session_judgement(
        self, frame: np.ndarray, mode: GameMode
    ) -> bool:
        return self._marker(frame) == 4

    async def extract_session_judgement(
        self, frame: np.ndarray, mode: GameMode
    ) -> Judgement:
        return Judgement.WIN


class _RateEvidenceAnalyzer(_EvidenceAnalyzer):
    async def extract_match_select(
        self, frame: np.ndarray, mode: GameMode
    ) -> Match | None:
        return Match.X

    async def extract_rate_for_match(
        self, frame: np.ndarray, mode: GameMode, match: object
    ) -> RateBase | None:
        return XP(2000.0)


@pytest.mark.asyncio
async def test_source_time_regroups_outputs_and_evidence_uses_detection_frames(
    tmp_path: Path,
) -> None:
    repository = FileImportedVideoRepository(tmp_path)
    service = ImportedVideoService(
        repository,
        _Reader(),
        _Probe(),
        cast(VideoEditorPort, _Editor()),
        cast(FramePreviewPort, _Editor()),
        cast(FrameAnalyzer, _RateEvidenceAnalyzer()),
        SubtitleConverter(),
        _WeaponFactory(),
        _Logger(),
        _Renderer(),
    )
    job = await service.create_import(
        "2026-10-23 22-59-07.mp4", ".mp4", _source_chunks()
    )
    job = await service.wait_for_scan(job.id)
    assert job.source_started_at == "2026-10-23T22:59:07"
    assert job.source_started_at_inferred
    candidate = job.candidates[0]
    assert candidate.metadata["started_at"] == "2026-10-23T22:59:08"
    assert candidate.evidence_seconds["judgement"] == 5.0
    assert candidate.evidence_seconds["result"] == 8.0
    assert candidate.evidence_seconds["rate"] == 0.0
    assert candidate.evidence_assets["rate"].endswith("/rate.png")
    rate_path = repository.asset_path(
        job.id, candidate.evidence_assets["rate"].replace("/", ":")
    )
    assert rate_path is not None
    import cv2

    assert np.all(cv2.imread(str(rate_path)) == 0)
    for kind, marker in (("judgement", 4), ("result", 6)):
        import cv2

        path = repository.asset_path(
            job.id, candidate.evidence_assets[kind].replace("/", ":")
        )
        assert path is not None
        evidence_image = cv2.imread(str(path))
        assert np.all(evidence_image == marker)
        if kind == "result":
            assert evidence_image.shape == (200, 800, 3)
    updated = service.update_source_time(job.id, "2026-10-24T00:00")
    assert (
        updated.candidates[0].metadata["started_at"] == "2026-10-24T00:00:01"
    )
    assert not updated.source_started_at_inferred
    metadata_path = repository.asset_path(
        job.id, f"candidate:{candidate.id}:metadata.json"
    )
    assert metadata_path is not None
    assert (
        json.loads(metadata_path.read_text(encoding="utf-8"))["started_at"]
        == updated.candidates[0].metadata["started_at"]
    )
    checkpoint = metadata_path.with_name("candidate.json")
    assert (
        json.loads(checkpoint.read_text(encoding="utf-8"))["metadata"][
            "started_at"
        ]
        == updated.candidates[0].metadata["started_at"]
    )
    # 同じ候補を別時刻帯として保存し、通常の時刻帯分割で別成果物になることを確認する。
    second_id = str(uuid4())
    staging = repository.candidate_staging_directory(job.id, second_id)
    repository.write_staging_file(job.id, staging, "video.mp4", b"second clip")
    second = replace(
        candidate,
        id=second_id,
        start_seconds=7201,
        end_seconds=7210,
        metadata={**candidate.metadata, "started_at": "2026-10-24T02:00:01"},
    )
    repository.commit_candidate(job.id, second, second_id, staging)
    repository.save_job(
        replace(updated, candidates=(updated.candidates[0], second))
    )
    completed = await service.edit_selected(job.id)
    assert len(completed.outputs) == 2
    assert {item.candidate_ids for item in completed.outputs} == {
        (candidate.id,),
        (second.id,),
    }
    edited = service.update_output_text(
        job.id, completed.outputs[0].id, "訂正タイトル", "訂正説明"
    )
    restored = repository.get_job(job.id)
    assert restored is not None
    assert (
        edited.outputs[0].title == restored.outputs[0].title == "訂正タイトル"
    )
    assert repository.source_path(job.id).read_bytes() == b"untouched source"


@pytest.mark.asyncio
async def test_start_edit_rejects_missing_source_time_before_changing_state(
    tmp_path: Path,
) -> None:
    repository = FileImportedVideoRepository(tmp_path)
    service = ImportedVideoService(
        repository,
        _Reader(),
        _Probe(),
        cast(VideoEditorPort, _Editor()),
        cast(FramePreviewPort, _Editor()),
        cast(FrameAnalyzer, _Analyzer()),
        SubtitleConverter(),
        _WeaponFactory(),
        _Logger(),
        _Renderer(),
    )
    job = await service.create_import("unknown.mp4", ".mp4", _source_chunks())
    job = await service.wait_for_scan(job.id)
    with pytest.raises(ValueError, match="元動画の開始日時"):
        service.start_edit(job.id)
    restored = repository.get_job(job.id)
    assert restored is not None and restored.state == "ready"
    with pytest.raises(ValueError, match="元動画の開始日時"):
        service.update_source_time(job.id, "invalid")


@pytest.mark.asyncio
async def test_weapon_evidence_prefers_visible_recognized_frame_over_finish_diagnostic() -> (
    None
):
    from splat_replay.application.services.imported_video_service import (
        _ImportedVideoWeaponRecognizer,
    )

    class Recognizer(_WeaponRecognizer):
        async def detect_weapon_display_details(
            self, frame: np.ndarray
        ) -> WeaponDisplayDetectionResult:
            marker = int(frame[0, 0, 0])
            return WeaponDisplayDetectionResult(
                is_visible=marker == 1, should_recognize=marker in {1, 2}
            )

    recognizer = _ImportedVideoWeaponRecognizer(Recognizer())
    for marker in (2, 1, 2, 3):
        frame = np.full((2, 2, 3), marker, dtype=np.uint8)
        recognizer.remember_frame(frame, float(marker))
        await recognizer.detect_weapon_display_details(frame)
        await recognizer.recognize_weapons(frame)
    assert recognizer.evidence_frame is not None
    assert np.all(recognizer.evidence_frame == 1)
    assert recognizer.evidence_seconds == 1.0
    # 表示未確認の終了時診断入力だけなら確認画像を捏造しない。
    recognizer = _ImportedVideoWeaponRecognizer(Recognizer())
    invisible = np.full((2, 2, 3), 3, dtype=np.uint8)
    await recognizer.detect_weapon_display_details(invisible)
    await recognizer.recognize_weapons(invisible)
    assert recognizer.evidence_frame is None


@pytest.mark.asyncio
async def test_offline_scan_waits_for_recognition_before_advancing_video_time(
    tmp_path: Path,
) -> None:
    import threading

    class Reader(_Reader):
        def __init__(self) -> None:
            super().__init__()
            self.positions: list[float] = []

        def frames(
            self, path: Path, sample_interval_seconds: float
        ) -> AsyncIterator[tuple[float, np.ndarray]]:
            async def iterate() -> AsyncIterator[tuple[float, np.ndarray]]:
                async for seconds, frame in super(Reader, self).frames(
                    path, sample_interval_seconds
                ):
                    self.positions.append(seconds)
                    yield seconds, frame

            return iterate()

    class Recognizer(_WeaponRecognizer):
        def __init__(self) -> None:
            super().__init__()
            self.started = threading.Event()
            self.release = threading.Event()

        def request_cancel(self) -> None:
            self.release.set()

        async def detect_weapon_display_details(
            self, frame: np.ndarray
        ) -> WeaponDisplayDetectionResult:
            self.started.set()
            assert await asyncio.to_thread(self.release.wait, 5)
            return await super().detect_weapon_display_details(frame)

    class Factory(_WeaponFactory):
        def __init__(self) -> None:
            super().__init__()
            self.recognizer = Recognizer()

    repository = FileImportedVideoRepository(tmp_path)
    reader = Reader()
    factory = Factory()
    recognizer = factory.recognizer
    assert isinstance(recognizer, Recognizer)
    service = ImportedVideoService(
        repository,
        reader,
        _Probe(),
        cast(VideoEditorPort, _Editor()),
        cast(FramePreviewPort, _Editor()),
        cast(FrameAnalyzer, _Analyzer()),
        SubtitleConverter(),
        factory,
        _Logger(),
        _Renderer(),
    )
    job = await service.create_import("source.mp4", ".mp4", _source_chunks())
    try:
        assert await asyncio.to_thread(recognizer.started.wait, 3)
        assert reader.positions == [0.0, 1.0]
    finally:
        recognizer.release.set()
    completed = await service.wait_for_scan(job.id)
    assert completed.state == "ready"
    assert completed.candidates[0].evidence_seconds["weapons"] == 1.0
    assert completed.candidates[0].metadata["allies"] == [
        "ブキ0",
        "ブキ1",
        "ブキ2",
        "ブキ3",
    ]


@pytest.mark.asyncio
async def test_missing_result_requires_complete_manual_fields_and_persists_valid_input(
    tmp_path: Path,
) -> None:
    repository = FileImportedVideoRepository(tmp_path)
    service = ImportedVideoService(
        repository,
        _Reader(),
        _Probe(),
        cast(VideoEditorPort, _Editor()),
        cast(FramePreviewPort, _Editor()),
        cast(FrameAnalyzer, _Analyzer()),
        SubtitleConverter(),
        _WeaponFactory(),
        _Logger(),
        _Renderer(),
    )
    job = await service.create_import("source.mp4", ".mp4", _source_chunks())
    job = await service.wait_for_scan(job.id)
    candidate = replace(job.candidates[0], metadata={"game_mode": "BATTLE"})
    repository.save_job(replace(job, candidates=(candidate,)))
    patch: dict[str, object] = {
        "match": "X",
        "rule": "SPLAT_ZONES",
        "stage": "SCORCH_GORGE",
        "kill": 9,
        "death": 3,
        "special": 2,
        "gold_medals": 2,
        "silver_medals": 1,
    }
    for invalid in (
        {"kill": 9},
        {**patch, "rule": "invalid"},
        {**patch, "death": None},
    ):
        with pytest.raises(ValueError, match="リザルト未取得"):
            service.update_candidate(job.id, candidate.id, invalid, None, None)
        unchanged = repository.get_job(job.id)
        assert unchanged is not None and unchanged.candidates[0].metadata == {
            "game_mode": "BATTLE"
        }
    updated = service.update_candidate(job.id, candidate.id, patch, None, None)
    for key, value in patch.items():
        assert updated.candidates[0].metadata[key] == value
    metadata_path = repository.asset_path(
        job.id, f"candidate:{candidate.id}:metadata.json"
    )
    assert metadata_path is not None
    assert json.loads(metadata_path.read_text(encoding="utf-8"))["kill"] == 9
    assert repository.source_path(job.id).read_bytes() == b"untouched source"
