"""実編集後の保持と、保持失敗後に再編集しない復旧を守る。"""

from __future__ import annotations

import hashlib
import json
import shutil
import socket
import subprocess
from datetime import datetime
from pathlib import Path
from typing import cast
from unittest.mock import MagicMock

import numpy as np
import pytest
import structlog

from splat_replay.application.interfaces import (
    ConfigPort,
    EventPublisher,
    LoggerPort,
    PathsPort,
    TextToSpeechPort,
)
from splat_replay.application.services.common.progress import ProgressReporter
from splat_replay.application.services.editing.auto_editor import (
    AutoEditor,
    EditedCommitCleanupError,
)
from splat_replay.domain.config import VideoEditSettings, VideoStorageSettings
from splat_replay.domain.models import (
    BattleResult,
    Judgement,
    Match,
    RecordingMetadata,
    Rule,
    Stage,
)
from splat_replay.infrastructure.adapters.image.image_drawer import ImageDrawer
from splat_replay.infrastructure.adapters.image.thumbnail_rule_image_resolver import (
    ThumbnailRuleImageResolver,
)
from splat_replay.infrastructure.adapters.system.cross_cutting import (
    LocalFileSystemAdapter,
)
from splat_replay.infrastructure.adapters.text.subtitle_editor import (
    SubtitleEditor,
)
from splat_replay.infrastructure.adapters.video.ffmpeg_processor import (
    FFmpegProcessor,
)
from splat_replay.infrastructure.repositories.video_asset_repo import (
    FileVideoAssetRepository,
)

pytestmark = pytest.mark.contract
BACKEND_ROOT = Path(__file__).resolve().parents[2]


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _binary(name: str) -> str:
    binary = shutil.which(name)
    if binary is None:
        pytest.skip(f"保持・復旧の実編集試験には {name} が必要")
    assert binary is not None
    return binary


def _make_editor(
    repository: FileVideoAssetRepository, storage: VideoStorageSettings
) -> AutoEditor:
    logger = structlog.get_logger()
    config = MagicMock(spec=ConfigPort)
    config.get_video_storage_settings.return_value = storage
    config.get_video_edit_settings.return_value = VideoEditSettings()
    paths = MagicMock(spec=PathsPort)
    assets = BACKEND_ROOT / "assets" / "thumbnail"
    paths.get_thumbnail_assets_dir.return_value = assets
    paths.get_thumbnail_asset.side_effect = lambda name: assets / name
    speech = MagicMock(spec=TextToSpeechPort)
    speech.synthesize.side_effect = AssertionError("読み上げは無効")
    return AutoEditor(
        logger=logger,
        config=cast(ConfigPort, config),
        paths=cast(PathsPort, paths),
        video_editor=FFmpegProcessor(logger),
        subtitle_editor=SubtitleEditor(logger),
        image_selector=ImageDrawer.select_brightest_image,
        text_to_speech=cast(TextToSpeechPort, speech),
        rule_image_resolver=ThumbnailRuleImageResolver(),
        repo=repository,
        file_system=LocalFileSystemAdapter(),
        progress=ProgressReporter(
            cast(EventPublisher, MagicMock()), cast(LoggerPort, logger)
        ),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("interrupt_retention", [False, True])
async def test_real_edit_retains_sources_and_resumes_without_reediting(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    interrupt_retention: bool,
) -> None:
    ffmpeg = _binary("ffmpeg")
    ffprobe = _binary("ffprobe")
    original = tmp_path / "original.mp4"
    subprocess.run(
        [
            ffmpeg,
            "-nostdin",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=c=blue:s=1920x1080:r=30:d=1",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:sample_rate=48000:duration=1",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-shortest",
            str(original),
        ],
        check=True,
        capture_output=True,
        timeout=30,
    )
    original_hash = _hash(original)
    original_stat = original.stat()
    storage = VideoStorageSettings(
        base_dir=tmp_path / "storage", keep_recordings_after_edit=True
    )
    logger = structlog.get_logger()
    repository = FileVideoAssetRepository(storage, logger, MagicMock())
    source_hashes: dict[str, str] = {}
    for index in range(2):
        work = tmp_path / f"work-{index}.mp4"
        shutil.copy2(original, work)
        metadata = RecordingMetadata(
            started_at=datetime(2026, 1, 1, 12, 0, index * 10),
            judgement=Judgement.WIN,
            result=BattleResult(
                match=Match.X,
                rule=Rule.SPLAT_ZONES,
                stage=Stage.UMAMI_RUINS,
                kill=1,
                death=0,
                special=0,
            ),
        )
        asset = repository.save_recording(
            work, None, np.full((1080, 1920, 3), 90, dtype=np.uint8), metadata
        )
        source_hashes[asset.video.name] = _hash(asset.video)

    def forbid_network(*args: object, **kwargs: object) -> None:
        raise AssertionError("保持試験では外部へ接続しない")

    monkeypatch.setattr(socket.socket, "connect", forbid_network)
    editor = _make_editor(repository, storage)
    if interrupt_retention:
        rename = Path.rename

        def fail_video_move(path: Path, target: Path) -> Path:
            if path.parent == storage.recorded_dir and path.suffix == ".mp4":
                raise OSError("保持先への移動中断を注入")
            return rename(path, target)

        with monkeypatch.context() as failure:
            failure.setattr(Path, "rename", fail_video_move)
            with pytest.raises(EditedCommitCleanupError):
                await editor.execute()
        outputs = list(storage.edited_dir.glob("*.mp4"))
        assert len(outputs) == 1
        committed_hash = _hash(outputs[0])
        assert list(storage.recorded_dir.glob(".*.retention.json"))
        for name, digest in source_hashes.items():
            assert _hash(storage.recorded_dir / name) == digest
        resumed_repository = FileVideoAssetRepository(
            storage, logger, MagicMock()
        )
        editor = _make_editor(resumed_repository, storage)

        async def forbid_reedit(*args: object, **kwargs: object) -> None:
            raise AssertionError("確定済み出力の復旧では再編集しない")

        monkeypatch.setattr(editor.video_editor, "merge", forbid_reedit)
        monkeypatch.setattr(
            editor.video_editor, "embed_metadata", forbid_reedit
        )
        monkeypatch.setattr(
            editor.video_editor, "embed_metadata_and_thumbnail", forbid_reedit
        )
        await editor.execute()
        assert _hash(outputs[0]) == committed_hash
    else:
        await editor.execute()

    outputs = list(storage.edited_dir.glob("*.mp4"))
    assert len(outputs) == 1
    assert len(repository.list_edited()) == 1
    assert repository.list_recordings() == []
    assert not list(storage.recorded_dir.glob(".*.retention.json"))
    for name, digest in source_hashes.items():
        retained = storage.retained_recorded_dir / name
        assert _hash(retained) == digest
        assert retained.with_suffix(".png").is_file()
        assert retained.with_suffix(".json").is_file()
    output = outputs[0]
    assert output.with_suffix(".png").is_file()
    assert output.with_suffix(".json").is_file()
    probe = json.loads(
        subprocess.check_output(
            [
                ffprobe,
                "-v",
                "error",
                "-show_format",
                "-show_streams",
                "-of",
                "json",
                str(output),
            ],
            timeout=15,
        )
    )
    assert 1.9 <= float(probe["format"]["duration"]) <= 2.2
    assert {stream["codec_type"] for stream in probe["streams"]} >= {
        "video",
        "audio",
    }
    subprocess.run(
        [
            ffmpeg,
            "-nostdin",
            "-v",
            "error",
            "-i",
            str(output),
            "-map",
            "0:v:0",
            "-map",
            "0:a:0",
            "-f",
            "null",
            "-",
        ],
        check=True,
        capture_output=True,
        timeout=30,
    )
    assert _hash(original) == original_hash
    assert original.stat().st_size == original_stat.st_size
    assert original.stat().st_mtime_ns == original_stat.st_mtime_ns
