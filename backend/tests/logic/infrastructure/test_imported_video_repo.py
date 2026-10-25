"""持込動画の保存先分離とcommit後回復のlogic。"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

import pytest

from splat_replay.application.dto.imported_video import (
    ImportedBattleDTO,
)
from splat_replay.infrastructure.repositories.imported_video_repo import (
    FileImportedVideoRepository,
)


async def _chunks() -> AsyncIterator[bytes]:
    yield b"source-video"


@pytest.mark.asyncio
async def test_committed_candidate_and_newest_output_recover_before_manifest_save(
    tmp_path: Path,
) -> None:
    repository = FileImportedVideoRepository(tmp_path)
    job = await repository.create_job("持込動画.mp4", ".mp4", _chunks())
    initial = repository.get_job(job.id)
    assert initial is not None and initial.output_directory is None
    candidate_id = str(uuid4())
    candidate = ImportedBattleDTO(
        id=candidate_id,
        start_seconds=4.0,
        end_seconds=8.0,
        segments=((4.0, 6.0), (7.0, 8.0)),
        selected=True,
        metadata={"stage": "test"},
        title="対戦 1",
        description="説明",
        clip_ready=True,
        duration_seconds=3.0,
    )
    candidate_staging = repository.candidate_staging_directory(
        job.id, candidate_id
    )
    repository.write_staging_file(
        job.id, candidate_staging, "video.mp4", b"candidate-video"
    )
    repository.commit_candidate(
        job.id, candidate, candidate_id, candidate_staging
    )

    recovered = repository.get_job(job.id)
    assert recovered is not None
    assert recovered.candidates == (candidate,)

    # 利用者の選択はmarkerの初期値で上書きされない。
    deselected = replace(candidate, selected=False)
    repository.save_job(replace(recovered, candidates=(deselected,)))

    first_staging = repository.create_work_directory(job.id, "output")
    repository.write_staging_file(job.id, first_staging, "video.mp4", b"first")
    first_id = repository.commit_output(
        job.id,
        first_staging,
        {
            "created_at": "2026-10-23T10:00:00+00:00",
            "title": "first",
            "description": "first description",
            "has_thumbnail": False,
            "has_subtitle": False,
        },
    )
    first_completed = repository.get_job(job.id)
    assert first_completed is not None
    assert first_completed.output_directory == str(
        tmp_path / "imports" / job.id / "outputs"
    )
    repository.save_job(
        replace(
            first_completed,
            state="completed",
            has_output=True,
            output_id=first_id,
            title="first",
            description="first description",
        )
    )

    manifest = json.loads(
        (tmp_path / "imports" / job.id / "manifest.json").read_text()
    )
    assert "output_directory" not in manifest

    second_staging = repository.create_work_directory(job.id, "output")
    repository.write_staging_file(
        job.id, second_staging, "video.mp4", b"second"
    )
    second_id = repository.commit_output(
        job.id,
        second_staging,
        {
            "created_at": "2026-10-23T10:01:00+00:00",
            "title": "second",
            "description": "second description",
            "has_thumbnail": True,
            "has_subtitle": True,
        },
    )

    recovered_again = repository.get_job(job.id)
    assert recovered_again is not None
    assert recovered_again.state == "completed"
    assert recovered_again.output_id == second_id
    assert recovered_again.title == "second"
    assert recovered_again.has_thumbnail and recovered_again.has_subtitle
    assert recovered_again.candidates[0].selected is False
    assert repository.asset_path(job.id, f"output:{second_id}:video.mp4") == (
        tmp_path / "imports" / job.id / "outputs" / second_id / "video.mp4"
    )

    for output_id in (first_id, second_id):
        (
            tmp_path / "imports" / job.id / "outputs" / output_id / "video.mp4"
        ).unlink()
    missing_output = repository.get_job(job.id)
    assert (
        missing_output is not None and missing_output.output_directory is None
    )


@pytest.mark.asyncio
async def test_import_repository_rejects_symlink_escape_and_tampered_suffix(
    tmp_path: Path,
) -> None:
    repository = FileImportedVideoRepository(tmp_path)
    job = await repository.create_job("source.mp4", ".mp4", _chunks())
    outside = tmp_path / "outside.json"
    outside.write_text("preserve", encoding="utf-8")
    staging = repository.candidate_staging_directory(job.id, str(uuid4()))
    (staging / "metadata.json").symlink_to(outside)

    with pytest.raises(ValueError, match="取込フォルダ外"):
        repository.write_staging_file(
            job.id, staging, "metadata.json", "replacement"
        )
    assert outside.read_text(encoding="utf-8") == "preserve"
    repository.remove_candidate_staging_directory(staging)

    manifest_path = tmp_path / "imports" / job.id / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["source_suffix"] = "../../outside.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="形式"):
        repository.source_path(job.id)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("subtitle_exists", "stored_flag"), [(True, False), (False, True)]
)
async def test_candidate_subtitle_flag_recovers_after_partial_file_checkpoint_update(
    tmp_path: Path, subtitle_exists: bool, stored_flag: bool
) -> None:
    repository = FileImportedVideoRepository(tmp_path)
    job = await repository.create_job("playback.mp4", ".mp4", _chunks())
    candidate_id = str(uuid4())
    candidate = ImportedBattleDTO(
        id=candidate_id,
        start_seconds=1.0,
        end_seconds=3.0,
        segments=((1.0, 3.0),),
        selected=True,
        metadata={},
        clip_ready=True,
        duration_seconds=2.0,
        has_subtitle=stored_flag,
    )
    staging = repository.candidate_staging_directory(job.id, candidate_id)
    repository.write_staging_file(job.id, staging, "video.mp4", b"candidate")
    if subtitle_exists:
        repository.write_staging_file(
            job.id,
            staging,
            "subtitle.srt",
            "1\n00:00:00,000 --> 00:00:01,000\ntext\n",
        )
    repository.commit_candidate(job.id, candidate, candidate_id, staging)
    repository.save_job(replace(job, state="ready", candidates=(candidate,)))

    recovered = repository.get_job(job.id)

    assert recovered is not None
    assert recovered.candidates[0].has_subtitle is subtitle_exists
    manifest = json.loads(
        (tmp_path / "imports" / job.id / "manifest.json").read_text(
            encoding="utf-8"
        )
    )
    checkpoint = json.loads(
        (
            tmp_path
            / "imports"
            / job.id
            / "candidates"
            / candidate_id
            / "candidate.json"
        ).read_text(encoding="utf-8")
    )
    assert manifest["candidates"][0]["has_subtitle"] is subtitle_exists
    assert checkpoint["has_subtitle"] is subtitle_exists


@pytest.mark.asyncio
async def test_existing_evidence_adds_exact_slot_and_medal_crops_once_and_keeps_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import cv2
    import numpy as np
    from splat_replay.infrastructure.adapters.weapon_detection.constants import (
        SLOT_BOXES,
    )
    from splat_replay.infrastructure.adapters.medal_detection.recognizer import (
        MEDAL_ROI,
    )

    repository = FileImportedVideoRepository(tmp_path)
    job = await repository.create_job("original.mp4", ".mp4", _chunks())
    candidate_id = str(uuid4())
    staging = repository.candidate_staging_directory(job.id, candidate_id)
    frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
    for index, (x1, y1, x2, y2) in enumerate(SLOT_BOXES.values(), start=1):
        frame[y1:y2, x1:x2] = index * 20
    x1, y1, x2, y2 = MEDAL_ROI
    frame[y1:y2, x1:x2] = 213
    repository.save_evidence_frame(job.id, staging, "weapons", frame)
    repository.save_evidence_frame(job.id, staging, "result-full", frame)
    repository.write_staging_file(job.id, staging, "video.mp4", b"candidate")
    candidate = ImportedBattleDTO(
        candidate_id,
        1,
        5,
        ((1, 5),),
        True,
        {},
        evidence_assets={"weapons": f"candidate/{candidate_id}/weapons.png"},
        evidence_seconds={"weapons": 1.5, "result": 4.5},
    )
    repository.commit_candidate(job.id, candidate, candidate_id, staging)
    repository.save_job(replace(job, candidates=(candidate,), state="ready"))
    restored = repository.get_job(job.id)
    assert restored is not None
    candidate = restored.candidates[0]
    assert candidate.evidence_sizes["weapons"] == (920, 120)
    assert candidate.evidence_sizes["result_full"] == (1920, 1080)
    assert candidate.evidence_regions["weapons"]["allies_0"] == (
        20,
        10,
        90,
        100,
    )
    assert candidate.evidence_regions["result_full"]["gold_medals"] == (
        x1,
        y1,
        x2 - x1,
        y2 - y1,
    )
    times: dict[str, int] = {}
    for index, slot in enumerate(SLOT_BOXES, start=1):
        kind = f"weapons_{slot}"
        path = repository.asset_path(
            job.id, candidate.evidence_assets[kind].replace("/", ":")
        )
        assert path is not None
        image = cv2.imread(str(path))
        assert image.shape == (100, 90, 3)
        assert np.all(image == index * 20)
        assert candidate.evidence_seconds[kind] == 1.5
        times[kind] = path.stat().st_mtime_ns
    medals = repository.asset_path(
        job.id, candidate.evidence_assets["medals"].replace("/", ":")
    )
    assert medals is not None
    image = cv2.imread(str(medals))
    assert image.shape == (280, 490, 3)
    assert np.all(image == 213)
    assert (
        candidate.evidence_seconds["medals"]
        == candidate.evidence_seconds["result_full"]
        == 4.5
    )
    assert "rate" not in candidate.evidence_assets
    assert repository.get_job(job.id) == restored
    for kind, previous_mtime in times.items():
        path = repository.asset_path(
            job.id, candidate.evidence_assets[kind].replace("/", ":")
        )
        assert path is not None and path.stat().st_mtime_ns == previous_mtime
    assert repository.source_path(job.id).read_bytes() == b"source-video"

    # 画像の追加保存だけ失敗しても候補・原本は読み出せ、未生成画像を露出しない。
    for kind in (*times, "medals"):
        path = repository.asset_path(
            job.id, candidate.evidence_assets[kind].replace("/", ":")
        )
        assert path is not None
        path.unlink()

    def fail_image_write(path: Path, content: bytes | str) -> None:
        raise OSError("確認画像の書き込み失敗")

    monkeypatch.setattr(repository, "_write_atomic_content", fail_image_write)
    unavailable = repository.get_job(job.id)
    assert unavailable is not None and len(unavailable.candidates) == 1
    assert "weapons" in unavailable.candidates[0].evidence_assets
    assert "result_full" in unavailable.candidates[0].evidence_assets
    assert "medals" not in unavailable.candidates[0].evidence_assets
    assert not any(
        key.startswith("weapons_")
        for key in unavailable.candidates[0].evidence_assets
    )
    assert repository.source_path(job.id).read_bytes() == b"source-video"


def test_evidence_template_location_uses_adopted_value_and_threshold(
    tmp_path: Path,
) -> None:
    import cv2
    import numpy as np
    from splat_replay.infrastructure.filesystem.paths import ASSETS_DIR
    from splat_replay.infrastructure.matchers.utils import imread_unicode
    from splat_replay.infrastructure.repositories.imported_video_evidence import (
        build_evidence_annotations,
    )

    template = imread_unicode(
        ASSETS_DIR / "matching/battle_rule_splat_zones.png"
    )
    assert template is not None
    frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
    height, width = template.shape[:2]
    frame[150 : 150 + height, 250 : 250 + width] = template
    path = tmp_path / "result.png"
    assert cv2.imwrite(str(path), frame)
    regions, sizes = build_evidence_annotations(
        {"result_full": path}, {"rule": "SPLAT_ZONES"}
    )
    assert sizes["result_full"] == (1920, 1080)
    assert regions["result_full"]["rule"] == (250, 150, width, height)
    assert cv2.imwrite(str(path), np.zeros_like(frame))
    regions, _ = build_evidence_annotations(
        {"result_full": path}, {"rule": "SPLAT_ZONES"}
    )
    assert "rule" not in regions["result_full"]
