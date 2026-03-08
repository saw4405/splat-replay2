"""録画済みビデオ DTO の Web API 変換。"""

from __future__ import annotations

from splat_replay.application.dto import RecordedVideoDTO
from splat_replay.interface.web.schemas import RecordedVideoItem


def to_recorded_video_item(dto: RecordedVideoDTO) -> RecordedVideoItem:
    """Application DTO を Interface DTO へ変換する。"""

    return RecordedVideoItem(
        id=dto.video_id,
        path=dto.path,
        filename=dto.filename,
        started_at=dto.started_at,
        game_mode=dto.game_mode,
        match=dto.match,
        rule=dto.rule,
        stage=dto.stage,
        rate=dto.rate,
        judgement=dto.judgement,
        kill=dto.kill,
        death=dto.death,
        special=dto.special,
        gold_medals=dto.gold_medals,
        silver_medals=dto.silver_medals,
        allies=dto.allies,
        enemies=dto.enemies,
        hazard=dto.hazard,
        golden_egg=dto.golden_egg,
        power_egg=dto.power_egg,
        rescue=dto.rescue,
        rescued=dto.rescued,
        has_subtitle=dto.has_subtitle,
        has_thumbnail=dto.has_thumbnail,
        duration_seconds=dto.duration_seconds,
        size_bytes=dto.size_bytes,
    )
