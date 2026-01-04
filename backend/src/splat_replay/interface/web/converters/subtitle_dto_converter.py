"""字幕DTOの変換ヘルパー。

責務:
- Application層のSubtitleDataDTOとInterface層のSubtitleData間の型変換のみ
- ビジネスロジックは含まない（フォーマット変換はapplication/services/common/subtitle_converterが担当）
"""

from __future__ import annotations

from splat_replay.application.dto import SubtitleBlockDTO, SubtitleDataDTO
from splat_replay.interface.web.schemas import SubtitleBlock, SubtitleData


def to_interface_subtitle_data(dto: SubtitleDataDTO) -> SubtitleData:
    """Application DTO → Interface DTOに変換。

    Args:
        dto: Application層のSubtitleDataDTO

    Returns:
        Interface層のSubtitleData
    """
    blocks = [
        SubtitleBlock(
            index=block.index,
            start_time=block.start_time,
            end_time=block.end_time,
            text=block.text,
        )
        for block in dto.blocks
    ]
    return SubtitleData(blocks=blocks, video_duration=dto.video_duration)


def to_application_subtitle_data(data: SubtitleData) -> SubtitleDataDTO:
    """Interface DTO → Application DTOに変換。

    Args:
        data: Interface層のSubtitleData

    Returns:
        Application層のSubtitleDataDTO
    """
    blocks = [
        SubtitleBlockDTO(
            index=block.index,
            start_time=block.start_time,
            end_time=block.end_time,
            text=block.text,
        )
        for block in data.blocks
    ]
    return SubtitleDataDTO(blocks=blocks, video_duration=data.video_duration)
