from __future__ import annotations

import asyncio
from pathlib import Path
from typing import cast
from unittest.mock import MagicMock

from pydantic import SecretStr
from splat_replay.application.interfaces.audio import TextToSpeechPort
from splat_replay.application.interfaces.common import (
    ConfigPort,
    FileSystemPort,
    LoggerPort,
)
from splat_replay.application.interfaces.image import SubtitleEditorPort
from splat_replay.application.interfaces.video import (
    VideoAssetRepositoryPort,
    VideoEditorPort,
)
from splat_replay.application.services.editing.subtitle_processor import (
    SubtitleProcessor,
)
from splat_replay.domain.config import VideoEditSettings
from splat_replay.domain.config.video_edit import SubtitleSpeechSettings


def test_tts_failure_log_contains_length_and_type_without_subtitle_text() -> (
    None
):
    logger = MagicMock()
    subtitle_text = "PRIVATE_SUBTITLE_SENTINEL"
    processor = object.__new__(SubtitleProcessor)
    processor.logger = cast(LoggerPort, logger)
    processor.settings = VideoEditSettings(
        speech=SubtitleSpeechSettings(
            enabled=True, google_api_key=SecretStr("not-used")
        )
    )
    processor.text_to_speech = cast(
        TextToSpeechPort,
        MagicMock(
            synthesize=MagicMock(
                side_effect=RuntimeError("REMOTE_BODY_SENTINEL")
            )
        ),
    )

    asyncio.run(
        processor._embed_subtitle_speech(
            None,
            f"1\n00:00:00,000 --> 00:00:01,000\n{subtitle_text}",
        )
    )

    logged = repr(logger.method_calls)
    assert subtitle_text not in logged
    assert "REMOTE_BODY_SENTINEL" not in logged
    assert f"text_length={len(subtitle_text)}" in logged
    assert "RuntimeError" in logged


def test_no_subtitle_keeps_editing_path_without_calling_tts() -> None:
    settings = VideoEditSettings(
        speech=SubtitleSpeechSettings(
            enabled=False, google_api_key=SecretStr("not-used")
        )
    )
    logger = MagicMock()
    config = MagicMock(
        get_video_edit_settings=MagicMock(return_value=settings)
    )
    subtitle_editor = MagicMock(merge=MagicMock(return_value=""))
    text_to_speech = MagicMock()
    processor = object.__new__(SubtitleProcessor)
    processor.logger = cast(LoggerPort, logger)
    processor.config = cast(ConfigPort, config)
    processor.settings = settings
    processor.subtitle_editor = cast(SubtitleEditorPort, subtitle_editor)
    processor.text_to_speech = cast(TextToSpeechPort, text_to_speech)
    processor.video_editor = cast(VideoEditorPort, object())
    processor.repo = cast(VideoAssetRepositoryPort, object())
    processor._file_system = cast(FileSystemPort, object())

    asyncio.run(processor.create_and_embed(Path("edited.mp4"), []))

    subtitle_editor.merge.assert_called_once_with([], [])
    text_to_speech.synthesize.assert_not_called()
