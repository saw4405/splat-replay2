from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, cast

import pytest
from structlog.stdlib import BoundLogger

from splat_replay.application.dto import RecordingMetadataPatchDTO
from splat_replay.application.interfaces import (
    FileStats,
    RecorderWithTranscriptionPort,
    VideoAssetRepositoryPort,
)
from splat_replay.application.services.common.battle_history_service import (
    BattleHistoryService,
)
from splat_replay.application.services.recording.recording_context import (
    RecordingContext,
)
from splat_replay.application.services.recording.recording_session_service import (
    RecordingSessionService,
)
from splat_replay.application.use_cases.metadata import (
    UpdateRecordedMetadataUseCase,
)
from splat_replay.domain.config import VideoStorageSettings
from splat_replay.domain.models import (
    BattleResult,
    GameMode,
    Judgement,
    Match,
    RecordingMetadata,
    Rule,
    Stage,
    VideoAsset,
)
from splat_replay.domain.services import (
    FrameAnalyzer,
    RecordState,
    StateMachine,
)
from splat_replay.infrastructure.adapters.storage.settings_repository import (
    TomlSettingsRepository,
)
from splat_replay.infrastructure.config import load_settings_from_toml
from splat_replay.infrastructure.repositories import (
    FileBattleHistoryRepository,
    FileVideoAssetRepository,
)


@dataclass
class _BehaviorSettings:
    edit_after_power_off: bool = True
    sleep_after_upload: bool = False
    record_battle_history: bool = True


class _DummyConfig:
    def __init__(self, *, record_battle_history: bool) -> None:
        self._behavior = _BehaviorSettings(
            record_battle_history=record_battle_history
        )

    def get_behavior_settings(self) -> _BehaviorSettings:
        return self._behavior

    def get_upload_settings(self):
        raise NotImplementedError

    def get_video_edit_settings(self):
        raise NotImplementedError

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


class _DummyLogger:
    def __init__(self) -> None:
        self.warnings: list[tuple[str, dict[str, object]]] = []

    def debug(self, event: str, **kw: object) -> None:
        _ = event, kw

    def info(self, event: str, **kw: object) -> None:
        _ = event, kw

    def warning(self, event: str, **kw: object) -> None:
        self.warnings.append((event, dict(kw)))

    def error(self, event: str, **kw: object) -> None:
        _ = event, kw

    def exception(self, event: str, **kw: object) -> None:
        _ = event, kw


class _DummyPublisher:
    def publish_domain_event(self, event: object) -> None:
        _ = event


class _HistorySpy:
    def __init__(self) -> None:
        self.calls: list[tuple[Path, RecordingMetadata]] = []

    def sync_recording(
        self, video_path: Path, metadata: RecordingMetadata
    ) -> None:
        self.calls.append((video_path, metadata))


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
        return 10.0

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


class _UpdateAssetRepository:
    def __init__(self, metadata: RecordingMetadata) -> None:
        self._metadata = metadata
        self.saved_metadata: RecordingMetadata | None = None

    def get_asset(self, video: Path) -> VideoAsset | None:
        return VideoAsset(video=video, metadata=self._metadata)

    def save_edited_metadata(
        self, video: Path, metadata: RecordingMetadata
    ) -> None:
        _ = video
        self.saved_metadata = metadata
        self._metadata = metadata

    def get_file_stats(self, video: Path) -> FileStats | None:
        _ = video
        return FileStats(size_bytes=123, updated_at=1.0)

    def has_subtitle(self, video: Path) -> bool:
        _ = video
        return False

    def has_thumbnail(self, video: Path) -> bool:
        _ = video
        return False


class _DummyStateMachine:
    def __init__(self) -> None:
        self.state = RecordState.RECORDING

    def add_listener(self, listener: object) -> None:
        _ = listener

    async def handle(self, event: object) -> None:
        _ = event
        self.state = RecordState.STOPPED


class _DummyRecorder:
    def __init__(self, video: Path) -> None:
        self._video = video

    def add_status_listener(self, listener: object) -> None:
        _ = listener

    async def stop(self) -> tuple[Path | None, Path | None]:
        return self._video, None


class _DummyAnalyzer:
    async def extract_session_result(
        self, frame: object, game_mode: GameMode
    ) -> BattleResult | None:
        _ = frame, game_mode
        raise AssertionError("extract_session_result は呼ばれない想定です。")


def _build_battle_result(
    *,
    kill: int = 7,
    death: int = 5,
    special: int = 2,
    gold_medals: int = 2,
    silver_medals: int = 1,
) -> BattleResult:
    return BattleResult(
        match=Match.X,
        rule=Rule.RAINMAKER,
        stage=Stage.HAMMERHEAD_BRIDGE,
        kill=kill,
        death=death,
        special=special,
        gold_medals=gold_medals,
        silver_medals=silver_medals,
    )


def _build_metadata(
    *,
    with_result: bool = True,
    result: BattleResult | None = None,
    judgement: Judgement | None = Judgement.WIN,
    allies: tuple[str, str, str, str] | None = (
        "スシ",
        "52ガロン",
        "ジム",
        "ラピ",
    ),
    enemies: tuple[str, str, str, str] | None = (
        "プライム",
        "ロング",
        "ハイドラ",
        "ボトル",
    ),
    game_mode: GameMode = GameMode.BATTLE,
) -> RecordingMetadata:
    return RecordingMetadata(
        game_mode=game_mode,
        started_at=datetime(2026, 3, 1, 12, 0, 0),
        judgement=judgement,
        allies=allies,
        enemies=enemies,
        result=(
            result
            if result is not None
            else (_build_battle_result() if with_result else None)
        ),
    )


def _read_history_file(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_settings_repository_exposes_and_persists_record_battle_history(
    tmp_path: Path,
) -> None:
    settings_path = tmp_path / "settings.toml"
    repository = TomlSettingsRepository(settings_path=settings_path)

    sections = repository.fetch_sections()
    behavior = next(
        section for section in sections if section["id"] == "behavior"
    )
    field = next(
        item
        for item in behavior["fields"]
        if item["id"] == "record_battle_history"
    )
    assert field["value"] is True

    repository.update_sections(
        [
            {
                "id": "behavior",
                "values": {
                    "edit_after_power_off": True,
                    "sleep_after_upload": False,
                    "record_battle_history": False,
                },
            }
        ]
    )

    settings = load_settings_from_toml(
        settings_path,
        create_if_missing=False,
    )
    assert settings.behavior.record_battle_history is False


def test_battle_history_service_creates_complete_record(
    tmp_path: Path,
) -> None:
    logger = _DummyLogger()
    settings = VideoStorageSettings(base_dir=tmp_path)
    repository = FileBattleHistoryRepository(
        settings,
        cast(BoundLogger, logger),
    )
    service = BattleHistoryService(
        repository=repository,
        config=_DummyConfig(record_battle_history=True),
        logger=logger,
        base_dir=tmp_path,
    )
    video_path = tmp_path / "recorded" / "battle1.mp4"
    video_path.parent.mkdir(parents=True, exist_ok=True)
    video_path.touch()

    service.sync_recording(video_path, _build_metadata())

    payload = _read_history_file(settings.battle_history_file)
    assert payload["version"] == 1
    records = cast(list[dict[str, Any]], payload["records"])
    assert len(records) == 1
    record = records[0]
    assert record["source_video_id"] == "recorded/battle1.mp4"
    assert record["match"] == "X"
    assert record["rule"] == "RAINMAKER"
    assert record["stage"] == "HAMMERHEAD_BRIDGE"
    assert record["judgement"] == "WIN"
    assert record["is_partial"] is False
    assert record["missing_fields"] == []


def test_battle_history_service_writes_to_separate_history_output(
    tmp_path: Path,
) -> None:
    logger = _DummyLogger()
    settings = VideoStorageSettings(base_dir=tmp_path / "videos")
    history_file = tmp_path / "outputs" / "history" / "battle_history.json"
    repository = FileBattleHistoryRepository(
        settings,
        cast(BoundLogger, logger),
        history_file=history_file,
    )
    service = BattleHistoryService(
        repository=repository,
        config=_DummyConfig(record_battle_history=True),
        logger=logger,
        base_dir=settings.base_dir,
    )
    video_path = settings.recorded_dir / "battle_outputs.mp4"
    video_path.parent.mkdir(parents=True, exist_ok=True)
    video_path.touch()

    service.sync_recording(video_path, _build_metadata())

    assert history_file.exists()
    assert not settings.battle_history_file.exists()
    payload = _read_history_file(history_file)
    records = cast(list[dict[str, Any]], payload["records"])
    assert records[0]["source_video_id"] == "recorded/battle_outputs.mp4"


def test_battle_history_service_marks_partial_record(
    tmp_path: Path,
) -> None:
    logger = _DummyLogger()
    settings = VideoStorageSettings(base_dir=tmp_path)
    repository = FileBattleHistoryRepository(
        settings,
        cast(BoundLogger, logger),
    )
    service = BattleHistoryService(
        repository=repository,
        config=_DummyConfig(record_battle_history=True),
        logger=logger,
        base_dir=tmp_path,
    )
    video_path = tmp_path / "recorded" / "battle2.mp4"
    video_path.parent.mkdir(parents=True, exist_ok=True)
    video_path.touch()
    metadata = _build_metadata(
        with_result=False,
        result=None,
        judgement=None,
        allies=("スシ", "", "ジム", "ラピ"),
        enemies=("不明", "ロング", "ハイドラ", "ボトル"),
    )

    service.sync_recording(video_path, metadata)

    payload = _read_history_file(settings.battle_history_file)
    records = cast(list[dict[str, Any]], payload["records"])
    record = records[0]
    assert record["allies"] == ["スシ", "", "ジム", "ラピ"]
    assert record["enemies"] == ["不明", "ロング", "ハイドラ", "ボトル"]
    assert record["is_partial"] is True
    assert set(record["missing_fields"]) == {
        "match",
        "rule",
        "stage",
        "kill",
        "death",
        "special",
        "gold_medals",
        "silver_medals",
        "judgement",
        "allies",
        "enemies",
    }


def test_battle_history_service_keeps_partial_battle_result_fields(
    tmp_path: Path,
) -> None:
    logger = _DummyLogger()
    settings = VideoStorageSettings(base_dir=tmp_path)
    repository = FileBattleHistoryRepository(
        settings,
        cast(BoundLogger, logger),
    )
    service = BattleHistoryService(
        repository=repository,
        config=_DummyConfig(record_battle_history=True),
        logger=logger,
        base_dir=tmp_path,
    )
    video_path = tmp_path / "recorded" / "battle_partial.mp4"
    video_path.parent.mkdir(parents=True, exist_ok=True)
    video_path.touch()
    metadata = _build_metadata(
        result=BattleResult(
            match=Match.X,
            rule=Rule.RAINMAKER,
            stage=None,
            kill=9,
            death=4,
            special=3,
            gold_medals=2,
            silver_medals=1,
        )
    )

    service.sync_recording(video_path, metadata)

    payload = _read_history_file(settings.battle_history_file)
    records = cast(list[dict[str, Any]], payload["records"])
    record = records[0]
    assert record["match"] == Match.X.name
    assert record["rule"] == Rule.RAINMAKER.name
    assert record["stage"] is None
    assert record["kill"] == 9
    assert record["death"] == 4
    assert record["special"] == 3
    assert record["is_partial"] is True
    assert "stage" in record["missing_fields"]


def test_battle_history_service_skips_new_record_when_disabled(
    tmp_path: Path,
) -> None:
    logger = _DummyLogger()
    settings = VideoStorageSettings(base_dir=tmp_path)
    repository = FileBattleHistoryRepository(
        settings,
        cast(BoundLogger, logger),
    )
    service = BattleHistoryService(
        repository=repository,
        config=_DummyConfig(record_battle_history=False),
        logger=logger,
        base_dir=tmp_path,
    )

    service.sync_recording(
        tmp_path / "recorded" / "disabled.mp4",
        _build_metadata(),
    )

    assert not settings.battle_history_file.exists()


def test_battle_history_service_updates_existing_record_when_disabled(
    tmp_path: Path,
) -> None:
    logger = _DummyLogger()
    settings = VideoStorageSettings(base_dir=tmp_path)
    repository = FileBattleHistoryRepository(
        settings,
        cast(BoundLogger, logger),
    )
    video_path = tmp_path / "recorded" / "battle3.mp4"
    video_path.parent.mkdir(parents=True, exist_ok=True)
    video_path.touch()

    enabled_service = BattleHistoryService(
        repository=repository,
        config=_DummyConfig(record_battle_history=True),
        logger=logger,
        base_dir=tmp_path,
    )
    disabled_service = BattleHistoryService(
        repository=repository,
        config=_DummyConfig(record_battle_history=False),
        logger=logger,
        base_dir=tmp_path,
    )

    enabled_service.sync_recording(video_path, _build_metadata())
    disabled_service.sync_recording(
        video_path,
        _build_metadata(
            judgement=Judgement.LOSE,
            result=_build_battle_result(kill=11, death=2),
        ),
    )

    payload = _read_history_file(settings.battle_history_file)
    records = cast(list[dict[str, Any]], payload["records"])
    assert len(records) == 1
    record = records[0]
    assert record["judgement"] == "LOSE"
    assert record["kill"] == 11
    assert record["death"] == 2


def test_battle_history_service_skips_non_battle_mode(
    tmp_path: Path,
) -> None:
    logger = _DummyLogger()
    settings = VideoStorageSettings(base_dir=tmp_path)
    repository = FileBattleHistoryRepository(
        settings,
        cast(BoundLogger, logger),
    )
    service = BattleHistoryService(
        repository=repository,
        config=_DummyConfig(record_battle_history=True),
        logger=logger,
        base_dir=tmp_path,
    )

    service.sync_recording(
        tmp_path / "recorded" / "salmon.mp4",
        _build_metadata(game_mode=GameMode.SALMON),
    )

    assert not settings.battle_history_file.exists()


def test_recorded_video_deletion_does_not_remove_history(
    tmp_path: Path,
) -> None:
    logger = _DummyLogger()
    settings = VideoStorageSettings(base_dir=tmp_path)
    history_repository = FileBattleHistoryRepository(
        settings,
        cast(BoundLogger, logger),
    )
    history_service = BattleHistoryService(
        repository=history_repository,
        config=_DummyConfig(record_battle_history=True),
        logger=logger,
        base_dir=tmp_path,
    )
    repository = FileVideoAssetRepository(
        settings,
        cast(BoundLogger, logger),
        _DummyPublisher(),
    )
    video_path = settings.recorded_dir / "battle4.mp4"
    video_path.parent.mkdir(parents=True, exist_ok=True)
    video_path.touch()

    history_service.sync_recording(video_path, _build_metadata())

    assert repository.delete_recording(video_path) is True
    assert settings.battle_history_file.exists()
    payload = _read_history_file(settings.battle_history_file)
    records = cast(list[dict[str, Any]], payload["records"])
    assert len(records) == 1


@pytest.mark.asyncio
async def test_update_recorded_metadata_use_case_syncs_history(
    tmp_path: Path,
) -> None:
    logger = _DummyLogger()
    history_spy = _HistorySpy()
    metadata = _build_metadata()
    repository = _UpdateAssetRepository(metadata)
    video_editor = _DummyVideoEditor()
    base_dir = tmp_path
    video_path = base_dir / "recorded" / "battle5.mp4"
    video_path.parent.mkdir(parents=True, exist_ok=True)
    video_path.touch()
    use_case = UpdateRecordedMetadataUseCase(
        repository=cast(VideoAssetRepositoryPort, repository),
        logger=logger,
        base_dir=base_dir,
        video_editor=video_editor,
        battle_history_service=cast(BattleHistoryService, history_spy),
    )

    dto = await use_case.execute(
        "recorded/battle5.mp4",
        RecordingMetadataPatchDTO(
            started_at="2026-03-05T23:45:01",
            judgement="LOSE",
            allies=("ヒッセン", "52ガロン", "ジム", "ラピ"),
        ),
    )

    assert dto.video_id == "recorded/battle5.mp4"
    assert repository.saved_metadata is not None
    assert repository.saved_metadata.started_at == datetime(
        2026, 3, 5, 23, 45, 1
    )
    assert repository.saved_metadata.judgement == Judgement.LOSE
    assert repository.saved_metadata.allies == (
        "ヒッセン",
        "52ガロン",
        "ジム",
        "ラピ",
    )
    assert history_spy.calls == [(video_path, repository.saved_metadata)]


@pytest.mark.asyncio
async def test_update_recorded_metadata_use_case_keeps_partial_battle_result(
    tmp_path: Path,
) -> None:
    logger = _DummyLogger()
    history_spy = _HistorySpy()
    metadata = _build_metadata()
    repository = _UpdateAssetRepository(metadata)
    video_editor = _DummyVideoEditor()
    base_dir = tmp_path
    video_path = base_dir / "recorded" / "battle_partial_recorded.mp4"
    video_path.parent.mkdir(parents=True, exist_ok=True)
    video_path.touch()
    use_case = UpdateRecordedMetadataUseCase(
        repository=cast(VideoAssetRepositoryPort, repository),
        logger=logger,
        base_dir=base_dir,
        video_editor=video_editor,
        battle_history_service=cast(BattleHistoryService, history_spy),
    )

    dto = await use_case.execute(
        "recorded/battle_partial_recorded.mp4",
        RecordingMetadataPatchDTO(stage=""),
    )

    assert dto.stage is None
    assert dto.kill == 7
    assert repository.saved_metadata is not None
    assert isinstance(repository.saved_metadata.result, BattleResult)
    assert repository.saved_metadata.result.stage is None
    assert repository.saved_metadata.result.kill == 7


@pytest.mark.asyncio
async def test_recording_session_service_syncs_history_after_save(
    tmp_path: Path,
) -> None:
    logger = _DummyLogger()
    history_spy = _HistorySpy()
    source_video = tmp_path / "capture.mp4"
    source_video.touch()
    saved_video = tmp_path / "recorded" / "battle6.mp4"

    class _AssetRepository:
        def save_recording(
            self,
            video: Path,
            srt: Path | None,
            screenshot: object,
            metadata: RecordingMetadata,
        ) -> VideoAsset:
            _ = video, srt, screenshot
            return VideoAsset(video=saved_video, metadata=metadata)

    service = RecordingSessionService(
        state_machine=cast(StateMachine, _DummyStateMachine()),
        recorder=cast(
            RecorderWithTranscriptionPort,
            _DummyRecorder(source_video),
        ),
        asset_repository=cast(VideoAssetRepositoryPort, _AssetRepository()),
        analyzer=cast(FrameAnalyzer, _DummyAnalyzer()),
        logger=logger,
        context=RecordingContext(
            metadata=_build_metadata(),
            battle_started_at=1.0,
        ),
        battle_history_service=cast(BattleHistoryService, history_spy),
    )

    async def _no_result_frame() -> None:
        return None

    await service.stop(_no_result_frame)

    assert len(history_spy.calls) == 1
    video_path, metadata = history_spy.calls[0]
    assert video_path == saved_video
    assert metadata.judgement == Judgement.WIN
