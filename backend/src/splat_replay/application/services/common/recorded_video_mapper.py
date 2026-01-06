"""Recorded video DTO mapper."""

from __future__ import annotations

from pathlib import Path

from splat_replay.application.dto import RecordedVideoDTO
from splat_replay.application.interfaces import (
    LoggerPort,
    VideoAssetRepositoryPort,
    VideoEditorPort,
)
from splat_replay.domain.models import (
    BattleResult,
    RecordingMetadata,
    SalmonResult,
)


async def build_recorded_video_dto(
    *,
    video_path: Path,
    metadata: RecordingMetadata,
    base_dir: Path,
    repository: VideoAssetRepositoryPort,
    video_editor: VideoEditorPort,
    logger: LoggerPort,
) -> RecordedVideoDTO:
    """Build RecordedVideoDTO from a recorded asset."""
    try:
        relative_path = video_path.relative_to(base_dir)
    except ValueError:
        logger.warning(
            "base_dir 外のファイルはスキップします",
            video=str(video_path),
            base_dir=str(base_dir),
        )
        # base_dir外の場合はファイル名のみを使用（後方互換性のため）
        relative_path = Path("recorded") / video_path.name

    duration_seconds: float | None = None
    try:
        duration_seconds = await video_editor.get_video_length(video_path)
    except Exception as exc:
        logger.warning(
            "動画の長さ取得失敗",
            video=str(video_path),
            error=str(exc),
        )

    file_stats = repository.get_file_stats(video_path)
    has_subtitle = repository.has_subtitle(video_path)
    has_thumbnail = repository.has_thumbnail(video_path)

    started_at = (
        metadata.started_at.isoformat() if metadata.started_at else None
    )
    game_mode = metadata.game_mode.value
    rate_value = str(metadata.rate) if metadata.rate else None
    judgement_value = metadata.judgement.value if metadata.judgement else None

    match_name: str | None = None
    rule_name: str | None = None
    stage_name: str | None = None
    kill_value: int | None = None
    death_value: int | None = None
    special_value: int | None = None
    hazard: int | None = None
    golden_egg: int | None = None
    power_egg: int | None = None
    rescue: int | None = None
    rescued: int | None = None

    if isinstance(metadata.result, BattleResult):
        match_name = metadata.result.match.value
        rule_name = metadata.result.rule.value
        stage_name = metadata.result.stage.value
        kill_value = metadata.result.kill
        death_value = metadata.result.death
        special_value = metadata.result.special
    elif isinstance(metadata.result, SalmonResult):
        stage_name = metadata.result.stage.value
        hazard = metadata.result.hazard
        golden_egg = metadata.result.golden_egg
        power_egg = metadata.result.power_egg
        rescue = metadata.result.rescue
        rescued = metadata.result.rescued

    return RecordedVideoDTO(
        video_id=str(relative_path.as_posix()),
        path=str(video_path),
        filename=video_path.name,
        started_at=started_at,
        game_mode=game_mode,
        match=match_name,
        rule=rule_name,
        stage=stage_name,
        rate=rate_value,
        judgement=judgement_value,
        kill=kill_value,
        death=death_value,
        special=special_value,
        hazard=hazard,
        golden_egg=golden_egg,
        power_egg=power_egg,
        rescue=rescue,
        rescued=rescued,
        has_subtitle=has_subtitle,
        has_thumbnail=has_thumbnail,
        duration_seconds=duration_seconds,
        size_bytes=file_stats.size_bytes if file_stats else None,
    )
