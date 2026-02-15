"""メタデータ・字幕管理ルーター。

責務：
- 現在の録画メタデータの取得・更新
- 録画済みビデオのメタデータ更新
- 録画済みビデオの字幕取得・更新
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, HTTPException, status
from splat_replay.application.dto import RecordingMetadataPatchDTO
from splat_replay.domain.exceptions import ValidationError
from splat_replay.domain.models import (
    GameMode,
    Judgement,
    Match,
    Rule,
    Stage,
)
from splat_replay.interface.web.converters import (
    to_application_subtitle_data,
    to_interface_subtitle_data,
)
from splat_replay.interface.web.schemas import (
    MetadataOptionItem,
    MetadataOptionsResponse,
    MetadataUpdateRequest,
    RecordedVideoItem,
    SubtitleData,
)

if TYPE_CHECKING:
    from splat_replay.interface.web.server import WebAPIServer


def create_metadata_router(server: WebAPIServer) -> APIRouter:
    """メタデータ・字幕管理ルーターを作成。

    Args:
        server: WebAPIServerインスタンス

    Returns:
        設定済みのAPIRouter
    """
    router = APIRouter(prefix="/api", tags=["metadata"])

    # === 録画済みビデオのメタデータ ===

    def _to_weapon_slots(
        value: list[str] | None,
    ) -> tuple[str, str, str, str] | None:
        if value is None:
            return None
        if len(value) != 4:
            return None
        return (value[0], value[1], value[2], value[3])

    @router.get(
        "/metadata/options",
        response_model=MetadataOptionsResponse,
    )
    async def get_metadata_options() -> MetadataOptionsResponse:
        """メタデータの選択肢を取得。"""
        return MetadataOptionsResponse(
            game_modes=[
                MetadataOptionItem(key=mode.name, label=mode.value)
                for mode in GameMode
            ],
            matches=[
                MetadataOptionItem(key=match.name, label=match.value)
                for match in Match
            ],
            rules=[
                MetadataOptionItem(key=rule.name, label=rule.value)
                for rule in Rule
            ],
            stages=[
                MetadataOptionItem(key=stage.name, label=stage.value)
                for stage in Stage
            ],
            judgements=[
                MetadataOptionItem(key=judgement.name, label=judgement.value)
                for judgement in Judgement
            ],
        )

    @router.patch(
        "/assets/recorded/{video_id:path}/metadata",
        response_model=RecordedVideoItem,
    )
    async def update_recorded_metadata(
        video_id: str, metadata: MetadataUpdateRequest
    ) -> RecordedVideoItem:
        """録画済みビデオのメタデータを更新。"""
        patch = RecordingMetadataPatchDTO(
            match=metadata.match,
            rule=metadata.rule,
            stage=metadata.stage,
            rate=metadata.rate,
            judgement=metadata.judgement,
            kill=metadata.kill,
            death=metadata.death,
            special=metadata.special,
            allies=_to_weapon_slots(metadata.allies),
            enemies=_to_weapon_slots(metadata.enemies),
        )
        try:
            dto = await server.update_recorded_metadata_uc.execute(
                video_id, patch
            )
        except FileNotFoundError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
            ) from exc
        except (ValueError, ValidationError) as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
            ) from exc
        except Exception as exc:
            server.logger.error(
                "録画メタデータ更新エラー", error=str(exc), video_id=video_id
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update metadata",
            ) from exc

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
            allies=list(dto.allies) if dto.allies else None,
            enemies=list(dto.enemies) if dto.enemies else None,
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

    # === 録画済みビデオの字幕 ===

    @router.get(
        "/subtitles/recorded/{video_id:path}",
        response_model=SubtitleData,
    )
    async def get_recorded_subtitle(video_id: str) -> SubtitleData:
        """録画済みビデオの字幕を取得。"""
        try:
            subtitle_data = (
                await server.get_recorded_subtitle_structured_uc.execute(
                    video_id
                )
            )
            return to_interface_subtitle_data(subtitle_data)
        except FileNotFoundError as e:
            # ファイルなしの場合は空の字幕データを返す
            server.logger.warning(f"字幕ファイルが見つかりません: {e}")
            return SubtitleData(blocks=[], video_duration=None)
        except ValueError as e:
            # SRTパースエラー
            server.logger.error(f"字幕のパースに失敗しました: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"字幕ファイルの形式が不正です: {str(e)}",
            ) from e

    @router.put(
        "/subtitles/recorded/{video_id:path}",
        response_model=SubtitleData,
    )
    async def update_recorded_subtitle(
        video_id: str, data: SubtitleData
    ) -> SubtitleData:
        """録画済みビデオの字幕を更新。"""
        subtitle_data = to_application_subtitle_data(data)
        await server.update_recorded_subtitle_structured_uc.execute(
            video_id, subtitle_data
        )
        return data

    return router


__all__ = ["create_metadata_router"]
