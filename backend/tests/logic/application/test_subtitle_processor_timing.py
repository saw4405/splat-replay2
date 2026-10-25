"""字幕のない候補も結合タイムラインの長さへ反映する。"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
import srt

from splat_replay.application.services.editing.subtitle_processor import (
    SubtitleProcessor,
)
from splat_replay.domain.config import VideoEditSettings
from splat_replay.domain.models import VideoAsset
from splat_replay.infrastructure.adapters.text.subtitle_editor import (
    SubtitleEditor,
)


@pytest.mark.asyncio
@pytest.mark.parametrize("missing_index", [0, 1])
@pytest.mark.parametrize("missing_file", [False, True])
async def test_subtitle_gaps_preserve_following_caption_time(
    tmp_path: Path, missing_index: int, missing_file: bool
) -> None:
    assets: list[VideoAsset] = []
    for index in range(3):
        subtitle = tmp_path / f"{index}.srt"
        if index != missing_index:
            subtitle.write_text(
                f"1\n00:00:01,000 --> 00:00:02,000\n候補{index}\n",
                encoding="utf-8",
            )
        assets.append(
            VideoAsset(
                video=tmp_path / f"{index}.mp4",
                subtitle=subtitle
                if missing_file or index != missing_index
                else None,
            )
        )
    saved = MagicMock()
    processor = SubtitleProcessor(
        logger=MagicMock(),
        config=MagicMock(
            get_video_edit_settings=MagicMock(return_value=VideoEditSettings())
        ),
        subtitle_editor=SubtitleEditor(MagicMock()),
        text_to_speech=MagicMock(),
        video_editor=MagicMock(get_video_length=AsyncMock(return_value=10.0)),
        repo=MagicMock(save_edited_subtitle=saved),
        file_system=MagicMock(is_file=MagicMock(side_effect=Path.is_file)),
    )

    merged = await processor._create_subtitle(tmp_path / "out.mp4", assets)

    captions = list(srt.parse(merged))
    assert [
        (caption.content, caption.start.total_seconds())
        for caption in captions
    ] == [
        (f"候補{index}", index * 10 + 1)
        for index in range(3)
        if index != missing_index
    ]
    saved.assert_called_once_with(tmp_path / "out.mp4", merged)
