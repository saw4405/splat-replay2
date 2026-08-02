from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import cast

import pytest

from splat_replay.application.interfaces import (
    ConfigPort,
    LoggerPort,
    VideoEditorPort,
)
from splat_replay.application.interfaces.data import (
    BehaviorSettingsView,
    CaptureDeviceSettingsView,
    OBSSettingsView,
    UploadSettingsView,
)
from splat_replay.application.services.editing.title_description_generator import (
    TitleDescriptionGenerator,
)
from splat_replay.domain.config.video_edit import VideoEditSettings
from splat_replay.domain.models import (
    BattleResult,
    GameMode,
    Judgement,
    Match,
    RecordingMetadata,
    Rule,
    Stage,
    VideoAsset,
    XP,
)
from splat_replay.domain.models.rate import RateBase


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

    def get_behavior_settings(self) -> BehaviorSettingsView:
        raise NotImplementedError

    def get_upload_settings(self) -> UploadSettingsView:
        raise NotImplementedError

    def get_video_edit_settings(self) -> VideoEditSettings:
        return self._settings

    def get_obs_settings(self) -> OBSSettingsView:
        raise NotImplementedError

    def save_obs_websocket_password(self, password: str) -> None:
        _ = password

    def get_capture_device_settings(self) -> CaptureDeviceSettingsView:
        raise NotImplementedError

    def save_capture_device_name(self, device_name: str) -> None:
        _ = device_name

    def save_capture_device_binding(
        self,
        device_name: str,
        hardware_id: str | None = None,
        location_path: str | None = None,
        parent_instance_id: str | None = None,
    ) -> None:
        _ = device_name, hardware_id, location_path, parent_instance_id

    def save_upload_privacy_status(self, privacy_status: str) -> None:
        _ = privacy_status


class _DummyVideoEditor:
    async def merge(
        self, clips: list[Path], output: Path, **kwargs: object
    ) -> Path:
        _ = clips, kwargs
        return output

    async def embed_metadata(
        self, path: Path, metadata: dict[str, str]
    ) -> None:
        _ = path, metadata

    async def embed_metadata_and_thumbnail(
        self,
        path: Path,
        metadata: dict[str, str],
        thumbnail: bytes,
        **kwargs: object,
    ) -> None:
        _ = path, metadata, thumbnail, kwargs

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


def _build_generator(title_template: str) -> TitleDescriptionGenerator:
    settings = VideoEditSettings(
        title_template=title_template,
        description_template="",
    )
    return TitleDescriptionGenerator(
        cast(LoggerPort, _DummyLogger()),
        cast(ConfigPort, _DummyConfig(settings)),
        cast(VideoEditorPort, _DummyVideoEditor()),
    )


def _build_asset(
    *,
    rate: RateBase | None = None,
    judgement: Judgement | None = Judgement.WIN,
    match: Match = Match.X,
    video: Path = Path("dummy.mp4"),
) -> VideoAsset:
    return VideoAsset(
        video=video,
        metadata=RecordingMetadata(
            game_mode=GameMode.BATTLE,
            started_at=dt.datetime(2026, 3, 1, 12, 0, 0),
            rate=rate,
            judgement=judgement,
            result=BattleResult(
                match=match,
                rule=Rule.RAINMAKER,
                stage=Stage.HAMMERHEAD_BRIDGE,
                kill=7,
                death=5,
                special=2,
            ),
        ),
    )


async def _generate_title(
    generator: TitleDescriptionGenerator,
    asset: VideoAsset,
) -> str:
    title, _ = await generator.generate(
        [asset],
        day=dt.date(2026, 3, 1),
        time_slot=dt.time(12, 0, 0),
    )
    return title


async def _generate_description(
    generator: TitleDescriptionGenerator,
    assets: list[VideoAsset],
) -> str:
    _, description = await generator.generate(
        assets,
        day=dt.date(2026, 3, 1),
        time_slot=dt.time(12, 0, 0),
    )
    return description


@pytest.mark.asyncio
async def test_generate_title_removes_empty_rate_parentheses() -> None:
    generator = _build_generator("{BATTLE}({RATE}) {RULE}")

    title = await _generate_title(generator, _build_asset(rate=None))

    assert title == f"{Match.X.value} {Rule.RAINMAKER.value}"


@pytest.mark.asyncio
async def test_generate_title_keeps_non_empty_rate_parentheses() -> None:
    generator = _build_generator("{BATTLE}({RATE}) {RULE}")

    title = await _generate_title(generator, _build_asset(rate=XP(2000.0)))

    assert title == f"{Match.X.value}(XP20) {Rule.RAINMAKER.value}"


@pytest.mark.parametrize(
    ("opening", "closing"),
    [
        ("(", ")"),
        ("（", "）"),
        ("[", "]"),
        ("［", "］"),
        ("【", "】"),
        ("「", "」"),
        ("『", "』"),
        ("<", ">"),
        ("〈", "〉"),
        ("《", "》"),
    ],
)
@pytest.mark.asyncio
async def test_generate_title_removes_empty_token_inside_major_brackets(
    opening: str,
    closing: str,
) -> None:
    generator = _build_generator(
        f"{{BATTLE}}{opening}{{RATE}}{closing}{{RULE}}"
    )

    title = await _generate_title(generator, _build_asset(rate=None))

    assert title == f"{Match.X.value}{Rule.RAINMAKER.value}"


@pytest.mark.asyncio
async def test_generate_title_removes_format_spec_padded_empty_token() -> None:
    generator = _build_generator("{BATTLE}({RATE:>5}) {RULE}")

    title = await _generate_title(generator, _build_asset(rate=None))

    assert title == f"{Match.X.value} {Rule.RAINMAKER.value}"


@pytest.mark.asyncio
async def test_generate_title_keeps_zero_value_inside_parentheses() -> None:
    generator = _build_generator("{BATTLE}({WIN}) {RULE}")

    title = await _generate_title(
        generator,
        _build_asset(rate=None, judgement=None),
    )

    assert title == f"{Match.X.value}(0) {Rule.RAINMAKER.value}"


@pytest.mark.asyncio
async def test_generate_title_keeps_literal_empty_parentheses() -> None:
    generator = _build_generator("{BATTLE}() {RULE}")

    title = await _generate_title(generator, _build_asset(rate=None))

    assert title == f"{Match.X.value}() {Rule.RAINMAKER.value}"


@pytest.mark.asyncio
async def test_generate_title_uses_event_power_label_for_event_match_rate() -> (
    None
):
    generator = _build_generator("{BATTLE}({RATE}) {RULE}")

    title = await _generate_title(
        generator,
        _build_asset(rate=XP(2180.0), match=Match.CHALLENGE),
    )

    assert (
        title
        == f"{Match.CHALLENGE.value}(最高イベントパワー: 2180.0) {Rule.RAINMAKER.value}"
    )


@pytest.mark.asyncio
async def test_generate_title_uses_highest_event_power_only_for_event_match() -> (
    None
):
    generator = _build_generator("{BATTLE}({RATE}) {RULE}")

    title, _ = await generator.generate(
        [
            _build_asset(
                rate=XP(2105.7),
                match=Match.CHALLENGE,
                video=Path("first.mp4"),
            ),
            _build_asset(
                rate=XP(2180.0),
                match=Match.CHALLENGE,
                video=Path("second.mp4"),
            ),
        ],
        day=dt.date(2026, 3, 1),
        time_slot=dt.time(12, 0, 0),
    )

    assert "最高イベントパワー: 2180.0" in title
    assert "2105.7-2180.0" not in title


@pytest.mark.asyncio
async def test_generate_description_includes_event_power_before_each_battle() -> (
    None
):
    settings = VideoEditSettings(
        title_template="{BATTLE} {RULE}",
        description_template="{CHAPTERS}",
        chapter_template="{RESULT:<5} {KILL:>3}k {DEATH:>3}d {SPECIAL:>3}s {STAGE}",
    )
    generator = TitleDescriptionGenerator(
        cast(LoggerPort, _DummyLogger()),
        cast(ConfigPort, _DummyConfig(settings)),
        cast(VideoEditorPort, _DummyVideoEditor()),
    )

    description = await _generate_description(
        generator,
        [
            _build_asset(
                rate=XP(2105.7),
                match=Match.CHALLENGE,
                video=Path("first.mp4"),
            ),
            _build_asset(
                rate=XP(2180.0),
                match=Match.CHALLENGE,
                video=Path("second.mp4"),
            ),
        ],
    )

    lines = description.splitlines()
    assert lines[0] == "最高イベントパワー: 2105.7"
    assert lines[1].startswith("00:00:00")
    assert lines[2] == "最高イベントパワー: 2180.0"
    assert lines[3].startswith("00:00:12")
    assert "XP:" not in description
