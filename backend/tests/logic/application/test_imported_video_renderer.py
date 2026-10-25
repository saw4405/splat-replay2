"""持込編集の成果物と作業領域内の保存を確認する。"""

from datetime import date, time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from splat_replay.application.services.editing.imported_video_renderer import (
    ImportedVideoRenderer,
)
from splat_replay.domain.config import VideoEditSettings


@pytest.mark.parametrize(
    ("with_thumbnail", "embed_failure"),
    [(True, False), (False, False), (True, True)],
)
@pytest.mark.asyncio
async def test_render_returns_local_sidecars_and_applies_edit_settings(
    tmp_path: Path,
    with_thumbnail: bool,
    embed_failure: bool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "output.mp4"
    thumbnail_path = tmp_path / "temporary.png"
    thumbnail_path.write_bytes(b"thumbnail")
    srt = "1\n00:00:00,000 --> 00:00:01,000\n字幕\n"
    fs = MagicMock(
        is_file=MagicMock(side_effect=Path.is_file),
        write_text=MagicMock(
            side_effect=lambda path, content: path.write_text(content)
        ),
        read_bytes=MagicMock(side_effect=Path.read_bytes),
        unlink=MagicMock(
            side_effect=lambda path, **kwargs: path.unlink(**kwargs)
        ),
    )
    config = MagicMock(
        get_video_edit_settings=MagicMock(
            return_value=VideoEditSettings(volume_multiplier=1.5)
        )
    )
    video_editor = MagicMock(
        embed_metadata=AsyncMock(),
        embed_metadata_and_thumbnail=AsyncMock(),
        change_volume=AsyncMock(),
    )
    renderer = ImportedVideoRenderer(
        logger=MagicMock(),
        config=config,
        paths=MagicMock(),
        video_editor=video_editor,
        subtitle_editor=MagicMock(merge=MagicMock(return_value=srt)),
        image_selector=MagicMock(),
        text_to_speech=MagicMock(),
        rule_image_resolver=MagicMock(),
        file_system=fs,
    )
    monkeypatch.setattr(
        renderer.title_generator,
        "generate",
        AsyncMock(return_value=("題名", "説明")),
    )
    monkeypatch.setattr(
        renderer.thumbnail_generator,
        "create",
        MagicMock(return_value=thumbnail_path if with_thumbnail else None),
    )

    if embed_failure:
        video_editor.embed_metadata_and_thumbnail.side_effect = RuntimeError(
            "埋込失敗"
        )
        with pytest.raises(RuntimeError, match="埋込失敗"):
            await renderer.render(target, [], date(2026, 1, 1), time(10))
        assert not thumbnail_path.exists()
        assert target.with_suffix(".srt").read_text() == srt
        return

    result = await renderer.render(target, [], date(2026, 1, 1), time(10))

    assert (result.title, result.description, result.subtitle) == (
        "題名",
        "説明",
        srt,
    )
    assert result.thumbnail == (b"thumbnail" if with_thumbnail else None)
    assert target.with_suffix(".srt").read_text() == srt
    video_editor.change_volume.assert_awaited_once_with(target, 1.5)
    if with_thumbnail:
        assert not thumbnail_path.exists()
        video_editor.embed_metadata_and_thumbnail.assert_awaited_once_with(
            target, {"title": "題名", "description": "説明"}, b"thumbnail"
        )
    else:
        video_editor.embed_metadata.assert_awaited_once_with(
            target, {"title": "題名", "description": "説明"}
        )
