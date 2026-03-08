"""Recorded video DTO mapper."""

from __future__ import annotations

from pathlib import Path

from splat_replay.application.dto import RecordedVideoDTO
from splat_replay.application.interfaces import (
    LoggerPort,
    VideoAssetRepositoryPort,
    VideoEditorPort,
)
from splat_replay.application.metadata import recording_metadata_to_dict
from splat_replay.application.metadata.codec import MetadataValue
from splat_replay.domain.models import RecordingMetadata


def _as_str(value: MetadataValue | None) -> str | None:
    return value if isinstance(value, str) else None


def _as_int(value: MetadataValue | None) -> int | None:
    return value if isinstance(value, int) else None


def _as_str_list(value: MetadataValue | None) -> list[str] | None:
    if isinstance(value, list) and all(
        isinstance(item, str) for item in value
    ):
        return value
    return None


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

    payload = recording_metadata_to_dict(metadata)

    return RecordedVideoDTO(
        video_id=str(relative_path.as_posix()),
        path=str(video_path),
        filename=video_path.name,
        started_at=_as_str(payload.get("started_at")),
        game_mode=_as_str(payload.get("game_mode")),
        match=_as_str(payload.get("match")),
        rule=_as_str(payload.get("rule")),
        stage=_as_str(payload.get("stage")),
        rate=_as_str(payload.get("rate")),
        judgement=_as_str(payload.get("judgement")),
        kill=_as_int(payload.get("kill")),
        death=_as_int(payload.get("death")),
        special=_as_int(payload.get("special")),
        gold_medals=_as_int(payload.get("gold_medals")),
        silver_medals=_as_int(payload.get("silver_medals")),
        allies=_as_str_list(payload.get("allies")),
        enemies=_as_str_list(payload.get("enemies")),
        hazard=_as_int(payload.get("hazard")),
        golden_egg=_as_int(payload.get("golden_egg")),
        power_egg=_as_int(payload.get("power_egg")),
        rescue=_as_int(payload.get("rescue")),
        rescued=_as_int(payload.get("rescued")),
        has_subtitle=has_subtitle,
        has_thumbnail=has_thumbnail,
        duration_seconds=duration_seconds,
        size_bytes=file_stats.size_bytes if file_stats else None,
    )
