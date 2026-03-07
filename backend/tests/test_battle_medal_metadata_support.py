from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path
from typing import cast

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / "src"))

import pytest  # noqa: E402
from pydantic import ValidationError as PydanticValidationError  # noqa: E402

from splat_replay.application.interfaces import (  # noqa: E402
    ConfigPort,
    LoggerPort,
    VideoEditorPort,
)
from splat_replay.application.services.editing.metadata_parser import (  # noqa: E402
    MetadataParser,
)
from splat_replay.application.services.editing.title_description_generator import (  # noqa: E402
    TitleDescriptionGenerator,
)
from splat_replay.application.services.recording.metadata_merger import (  # noqa: E402
    MetadataMerger,
)
from splat_replay.domain.exceptions import (  # noqa: E402
    ValidationError as DomainValidationError,
)
from splat_replay.domain.config.video_edit import VideoEditSettings  # noqa: E402
from splat_replay.domain.models import (  # noqa: E402
    BattleResult,
    GameMode,
    Judgement,
    Match,
    RecordingMetadata,
    Rule,
    Stage,
    VideoAsset,
)
from splat_replay.interface.web.routers.recording import (  # noqa: E402
    RecordingMetadataUpdateRequest,
)
from splat_replay.interface.web.schemas.metadata import (  # noqa: E402
    MetadataUpdateRequest,
)


class _DummyLogger:
    def debug(self, event: str, **kw: object) -> None:
        _ = event, kw

    def info(self, event: str, **kw: object) -> None:
        _ = event, kw

    def warning(self, event: str, **kw: object) -> None:
        _ = event, kw

    def error(self, event: str, **kw: object) -> None:
        _ = event, kw

    def exception(self, event: str, **kw: object) -> None:
        _ = event, kw


class _DummyConfig:
    def __init__(self, settings: VideoEditSettings) -> None:
        self._settings = settings

    def get_behavior_settings(self):
        raise NotImplementedError

    def get_upload_settings(self):
        raise NotImplementedError

    def get_video_edit_settings(self) -> VideoEditSettings:
        return self._settings

    def get_obs_settings(self):
        raise NotImplementedError

    def save_obs_websocket_password(self, password: str) -> None:
        _ = password

    def get_capture_device_settings(self):
        raise NotImplementedError

    def save_capture_device_name(self, device_name: str) -> None:
        _ = device_name

    def save_upload_privacy_status(self, privacy_status: str) -> None:
        _ = privacy_status


class _DummyVideoEditor:
    async def merge(self, clips: list[Path], output: Path) -> Path:
        _ = clips
        return output

    async def embed_metadata(
        self, path: Path, metadata: dict[str, str]
    ) -> None:
        _ = path, metadata

    async def get_metadata(self, path: Path) -> dict[str, str]:
        _ = path
        return {}

    async def embed_subtitle(self, path: Path, srt: str) -> None:
        _ = path, srt

    async def get_subtitle(self, path: Path) -> str | None:
        _ = path
        return None

    async def embed_thumbnail(self, path: Path, thumbnail: bytes) -> None:
        _ = path, thumbnail

    async def get_thumbnail(self, path: Path) -> bytes | None:
        _ = path
        return None

    async def change_volume(self, path: Path, multiplier: float) -> None:
        _ = path, multiplier

    async def get_video_length(self, path: Path) -> float | None:
        _ = path
        return 12.0

    async def add_audio_track(
        self,
        path: Path,
        audio: Path,
        *,
        stream_title: str | None = None,
    ) -> None:
        _ = path, audio, stream_title

    async def list_video_devices(self) -> list[str]:
        return []


def _build_battle_result(
    *,
    gold_medals: int = 2,
    silver_medals: int = 1,
) -> BattleResult:
    return BattleResult(
        match=Match.X,
        rule=Rule.RAINMAKER,
        stage=Stage.HAMMERHEAD_BRIDGE,
        kill=7,
        death=5,
        special=2,
        gold_medals=gold_medals,
        silver_medals=silver_medals,
    )


def test_battle_result_from_dict_defaults_medals_to_zero() -> None:
    result = BattleResult.from_dict(
        {
            "match": "X",
            "rule": "RAINMAKER",
            "stage": "HAMMERHEAD_BRIDGE",
            "kill": 0,
            "death": 3,
            "special": 0,
        }
    )
    assert result.gold_medals == 0
    assert result.silver_medals == 0


@pytest.mark.parametrize(
    ("gold_medals", "silver_medals"),
    [
        (-1, 0),
        (0, -1),
        (4, 0),
        (0, 4),
        (2, 2),
    ],
)
def test_battle_result_rejects_invalid_medal_counts(
    gold_medals: int, silver_medals: int
) -> None:
    with pytest.raises(DomainValidationError):
        BattleResult(
            match=Match.X,
            rule=Rule.RAINMAKER,
            stage=Stage.HAMMERHEAD_BRIDGE,
            kill=7,
            death=5,
            special=2,
            gold_medals=gold_medals,
            silver_medals=silver_medals,
        )


def test_metadata_parser_rejects_invalid_partial_medal_update() -> None:
    current = _build_battle_result(gold_medals=2, silver_medals=1)

    with pytest.raises(DomainValidationError):
        MetadataParser.parse_battle_result_updates(
            current,
            {"gold_medals": 3},
        )


@pytest.mark.parametrize(
    "payload",
    [
        {"gold_medals": -1},
        {"silver_medals": 4},
        {"gold_medals": 2, "silver_medals": 2},
    ],
)
def test_metadata_update_request_rejects_invalid_medal_counts(
    payload: dict[str, int],
) -> None:
    with pytest.raises(PydanticValidationError):
        MetadataUpdateRequest.parse_obj(payload)


@pytest.mark.parametrize(
    "payload",
    [
        {"gold_medals": -1},
        {"silver_medals": 4},
        {"gold_medals": 2, "silver_medals": 2},
    ],
)
def test_recording_metadata_update_request_rejects_invalid_medal_counts(
    payload: dict[str, int],
) -> None:
    with pytest.raises(PydanticValidationError):
        RecordingMetadataUpdateRequest.parse_obj(payload)


def test_recording_metadata_round_trip_with_medals() -> None:
    metadata = RecordingMetadata(
        game_mode=GameMode.BATTLE,
        started_at=dt.datetime(2026, 3, 1, 12, 0, 0),
        judgement=Judgement.WIN,
        result=_build_battle_result(),
    )

    restored = MetadataParser.from_dict(metadata.to_dict())

    assert restored == metadata


def test_metadata_merger_preserves_manual_medal_fields() -> None:
    merger = MetadataMerger()
    base = _build_battle_result(gold_medals=1, silver_medals=1)
    auto = _build_battle_result(gold_medals=3, silver_medals=0)
    current = _build_battle_result(gold_medals=2, silver_medals=1)

    merged = merger._merge_battle_result(
        base,
        auto,
        current,
        frozenset({"gold_medals", "silver_medals"}),
    )

    assert merged.gold_medals == 2
    assert merged.silver_medals == 1


@pytest.mark.asyncio
async def test_title_description_generator_includes_medals() -> None:
    settings = VideoEditSettings(
        chapter_template=(
            "{RESULT:<5} {KILL:>3}k {DEATH:>3}d {SPECIAL:>3}s {MEDALS} {STAGE}"
        )
    )
    generator = TitleDescriptionGenerator(
        cast(LoggerPort, _DummyLogger()),
        cast(ConfigPort, _DummyConfig(settings)),
        cast(VideoEditorPort, _DummyVideoEditor()),
    )
    asset = VideoAsset(
        video=Path("dummy.mp4"),
        metadata=RecordingMetadata(
            game_mode=GameMode.BATTLE,
            started_at=dt.datetime(2026, 3, 1, 12, 0, 0),
            judgement=Judgement.WIN,
            result=_build_battle_result(gold_medals=2, silver_medals=1),
        ),
    )

    _, description = await generator.generate(
        [asset],
        day=dt.date(2026, 3, 1),
        time_slot=dt.time(12, 0, 0),
    )

    assert "🥇x2 🥈x1" in description
