from __future__ import annotations

import datetime as dt
import sys
from dataclasses import fields as dataclass_fields
from pathlib import Path

import pytest

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / "src"))

pytestmark = pytest.mark.contract

from splat_replay.application.dto import (  # noqa: E402
    RecordedVideoDTO,
    RecordingMetadataPatchDTO,
)
from splat_replay.application.metadata import (  # noqa: E402
    BATTLE_METADATA_FIELDS,
    COMMON_METADATA_FIELDS,
    EDITABLE_METADATA_FIELDS,
    RECORDED_METADATA_PATCH_FIELDS,
    SALMON_METADATA_FIELDS,
    recording_metadata_to_dict,
)
from splat_replay.application.services.editing.metadata_parser import (  # noqa: E402
    MetadataParser,
)
from splat_replay.application.services.recording.metadata_merger import (  # noqa: E402
    MetadataMerger,
)
from splat_replay.domain.models import (  # noqa: E402
    BattleResult,
    GameMode,
    Judgement,
    Match,
    RecordingMetadata,
    Rule,
    SalmonResult,
    Stage,
)
from splat_replay.domain.models.rate import RateBase  # noqa: E402
from splat_replay.interface.web.converters import (  # noqa: E402
    to_recorded_video_item,
)
from splat_replay.interface.web.routers.recording import (  # noqa: E402
    RecordingMetadataResponse,
    RecordingMetadataUpdateRequest,
    _build_recording_metadata_response,
)
from splat_replay.interface.web.schemas.metadata import (  # noqa: E402
    MetadataUpdateRequest,
)


def test_recorded_metadata_request_matches_patch_dto_fields() -> None:
    dto_fields = {
        field.name for field in dataclass_fields(RecordingMetadataPatchDTO)
    }
    request_fields = set(MetadataUpdateRequest.__fields__.keys())
    assert request_fields == RECORDED_METADATA_PATCH_FIELDS
    assert dto_fields == RECORDED_METADATA_PATCH_FIELDS


def test_recorded_metadata_patch_dto_from_update_dict_normalises_weapon_slots() -> (
    None
):
    patch = RecordingMetadataPatchDTO.from_update_dict(
        {
            "started_at": "2026-03-01T12:34:56",
            "match": Match.X.name,
            "allies": ["A", "B", "C", "D"],
            "enemies": ["E", "F", "G", "H"],
            "ignored": "value",
        }
    )

    assert patch.started_at == "2026-03-01T12:34:56"
    assert patch.match == Match.X.name
    assert patch.allies == ("A", "B", "C", "D")
    assert patch.enemies == ("E", "F", "G", "H")


def test_recorded_metadata_patch_dto_to_metadata_update_dict_preserves_internal_types() -> (
    None
):
    patch = RecordingMetadataPatchDTO(
        started_at="2026-03-01T12:34:56",
        match=Match.X.name,
        allies=("A", "B", "C", "D"),
        enemies=("E", "F", "G", "H"),
    )

    assert patch.to_metadata_update_dict() == {
        "started_at": "2026-03-01T12:34:56",
        "match": Match.X.name,
        "allies": ("A", "B", "C", "D"),
        "enemies": ("E", "F", "G", "H"),
    }


def test_recording_metadata_response_matches_metadata_schema_fields() -> None:
    response_fields = set(RecordingMetadataResponse.__fields__.keys())
    expected_fields = (
        COMMON_METADATA_FIELDS
        | BATTLE_METADATA_FIELDS
        | SALMON_METADATA_FIELDS
    )
    assert response_fields == expected_fields


def test_live_recording_request_matches_metadata_schema_fields() -> None:
    request_fields = set(RecordingMetadataUpdateRequest.__fields__.keys())
    expected_fields = EDITABLE_METADATA_FIELDS
    assert request_fields == expected_fields


def test_live_recording_request_preserves_explicit_null_values() -> None:
    request = RecordingMetadataUpdateRequest(rate=None)

    assert request.dict(exclude_unset=True) == {"rate": None}


def test_recording_metadata_to_dict_uses_schema_for_battle() -> None:
    metadata = RecordingMetadata(
        game_mode=GameMode.BATTLE,
        started_at=dt.datetime(2026, 3, 1, 12, 0, 0),
        judgement=Judgement.WIN,
        allies=("A", "B", "C", "D"),
        enemies=("E", "F", "G", "H"),
        result=BattleResult(
            match=Match.X,
            rule=Rule.RAINMAKER,
            stage=Stage.HAMMERHEAD_BRIDGE,
            kill=7,
            death=5,
            special=2,
            gold_medals=2,
            silver_medals=1,
        ),
    )

    payload = recording_metadata_to_dict(metadata)

    assert (
        set(payload.keys()) == COMMON_METADATA_FIELDS | BATTLE_METADATA_FIELDS
    )


def test_recording_metadata_to_dict_uses_schema_for_salmon() -> None:
    metadata = RecordingMetadata(
        game_mode=GameMode.SALMON,
        started_at=dt.datetime(2026, 3, 1, 12, 0, 0),
        allies=("A", "B", "C", "D"),
        enemies=("E", "F", "G", "H"),
        result=SalmonResult(
            hazard=120,
            stage=Stage.HAMMERHEAD_BRIDGE,
            golden_egg=39,
            power_egg=1043,
            rescue=3,
            rescued=1,
        ),
    )

    payload = recording_metadata_to_dict(metadata)

    assert (
        set(payload.keys()) == COMMON_METADATA_FIELDS | SALMON_METADATA_FIELDS
    )


def test_recording_metadata_response_builder_uses_serialized_payload() -> None:
    metadata = RecordingMetadata(
        game_mode=GameMode.BATTLE,
        started_at=dt.datetime(2026, 3, 1, 12, 0, 0),
        judgement=Judgement.WIN,
        allies=("A", "B", "C", "D"),
        enemies=("E", "F", "G", "H"),
        result=BattleResult(
            match=Match.X,
            rule=Rule.RAINMAKER,
            stage=Stage.HAMMERHEAD_BRIDGE,
            kill=7,
            death=5,
            special=2,
            gold_medals=2,
            silver_medals=1,
        ),
    )

    response = _build_recording_metadata_response(metadata)

    assert response.dict(exclude_none=True) == {
        key: value
        for key, value in recording_metadata_to_dict(metadata).items()
        if value is not None
    }


def test_recording_metadata_to_dict_does_not_crash_on_mode_result_mismatch() -> (
    None
):
    metadata = RecordingMetadata(
        game_mode=GameMode.SALMON,
        started_at=dt.datetime(2026, 3, 1, 12, 0, 0),
        result=BattleResult(
            match=Match.X,
            rule=Rule.RAINMAKER,
            stage=Stage.HAMMERHEAD_BRIDGE,
            kill=7,
            death=5,
            special=2,
            gold_medals=2,
            silver_medals=1,
        ),
    )

    payload = recording_metadata_to_dict(metadata)

    assert (
        set(payload.keys()) == COMMON_METADATA_FIELDS | BATTLE_METADATA_FIELDS
    )


def test_recording_metadata_to_dict_keeps_partial_battle_result() -> None:
    metadata = RecordingMetadata(
        game_mode=GameMode.BATTLE,
        result=BattleResult(
            match=Match.X,
            rule=Rule.RAINMAKER,
            stage=None,
            kill=7,
            death=5,
            special=2,
            gold_medals=2,
            silver_medals=1,
        ),
    )

    payload = recording_metadata_to_dict(metadata)
    restored = MetadataParser.from_dict(payload)

    assert payload["stage"] is None
    assert isinstance(restored.result, BattleResult)
    assert restored.result.stage is None
    assert restored.result.kill == 7


def test_metadata_parser_clears_result_when_game_mode_changes() -> None:
    current = RecordingMetadata(
        game_mode=GameMode.BATTLE,
        result=BattleResult(
            match=Match.X,
            rule=Rule.RAINMAKER,
            stage=Stage.HAMMERHEAD_BRIDGE,
            kill=7,
            death=5,
            special=2,
            gold_medals=2,
            silver_medals=1,
        ),
    )

    updated = MetadataParser.parse_metadata_updates(
        current,
        {"game_mode": GameMode.SALMON.name},
    )

    assert updated.game_mode == GameMode.SALMON
    assert updated.result is None


def test_metadata_parser_clears_optional_common_field_when_given_none() -> (
    None
):
    current = RecordingMetadata(
        game_mode=GameMode.BATTLE,
        rate=RateBase.create("2500"),
    )

    updated, applied_fields = (
        MetadataParser.parse_metadata_updates_with_applied_fields(
            current,
            {"rate": None},
        )
    )

    assert updated.rate is None
    assert applied_fields == frozenset({"rate"})


def test_metadata_parser_clears_optional_common_field_when_given_empty_string() -> (
    None
):
    current = RecordingMetadata(
        game_mode=GameMode.BATTLE,
        started_at=dt.datetime(2026, 3, 1, 12, 0, 0),
        rate=RateBase.create("2500"),
        judgement=Judgement.WIN,
    )

    updated, applied_fields = (
        MetadataParser.parse_metadata_updates_with_applied_fields(
            current,
            {"started_at": "", "rate": "", "judgement": ""},
        )
    )

    assert updated.started_at is None
    assert updated.rate is None
    assert updated.judgement is None
    assert applied_fields == frozenset({"started_at", "rate", "judgement"})


def test_metadata_parser_keeps_existing_result_when_result_field_is_given_none() -> (
    None
):
    current = RecordingMetadata(
        game_mode=GameMode.BATTLE,
        result=BattleResult(
            match=Match.X,
            rule=Rule.RAINMAKER,
            stage=Stage.HAMMERHEAD_BRIDGE,
            kill=7,
            death=5,
            special=2,
            gold_medals=2,
            silver_medals=1,
        ),
    )
    current_result = current.result
    assert isinstance(current_result, BattleResult)

    updated, applied_fields = (
        MetadataParser.parse_metadata_updates_with_applied_fields(
            current,
            {"stage": None},
        )
    )

    assert isinstance(updated.result, BattleResult)
    assert updated.result.stage is None
    assert updated.result.kill == current_result.kill
    assert applied_fields == frozenset({"stage"})


def test_metadata_parser_keeps_existing_result_when_required_battle_field_is_empty() -> (
    None
):
    current = RecordingMetadata(
        game_mode=GameMode.BATTLE,
        result=BattleResult(
            match=Match.X,
            rule=Rule.RAINMAKER,
            stage=Stage.HAMMERHEAD_BRIDGE,
            kill=7,
            death=5,
            special=2,
            gold_medals=2,
            silver_medals=1,
        ),
    )
    current_result = current.result
    assert isinstance(current_result, BattleResult)

    updated, applied_fields = (
        MetadataParser.parse_metadata_updates_with_applied_fields(
            current,
            {"match": ""},
        )
    )

    assert isinstance(updated.result, BattleResult)
    assert updated.result.match is None
    assert updated.result.death == current_result.death
    assert applied_fields == frozenset({"match"})


def test_metadata_merger_keeps_partial_battle_result_when_field_is_cleared() -> (
    None
):
    merger = MetadataMerger()
    current = RecordingMetadata(
        game_mode=GameMode.BATTLE,
        result=BattleResult(
            match=Match.X,
            rule=Rule.RAINMAKER,
            stage=Stage.HAMMERHEAD_BRIDGE,
            kill=7,
            death=5,
            special=2,
            gold_medals=2,
            silver_medals=1,
        ),
    )
    current_result = current.result
    assert isinstance(current_result, BattleResult)

    for field, value in (
        ("match", ""),
        ("rule", None),
        ("stage", ""),
    ):
        updated, applied_fields = merger.apply_manual_updates(
            current, {field: value}
        )

        assert isinstance(updated.result, BattleResult)
        assert getattr(updated.result, field) is None
        assert updated.result.kill == current_result.kill
        assert applied_fields == frozenset({field})


def test_recorded_video_item_converter_stays_in_sync_with_recorded_video_dto() -> (
    None
):
    dto = RecordedVideoDTO(
        video_id="recorded/test.mp4",
        path=str(Path("/tmp/recorded/test.mp4")),
        filename="test.mp4",
        started_at="2026-03-01T12:00:00",
        game_mode=GameMode.BATTLE.name,
        match=Match.X.name,
        rule=Rule.RAINMAKER.name,
        stage=Stage.HAMMERHEAD_BRIDGE.name,
        rate="2500",
        judgement=Judgement.WIN.name,
        kill=7,
        death=5,
        special=2,
        gold_medals=2,
        silver_medals=1,
        allies=["A", "B", "C", "D"],
        enemies=["E", "F", "G", "H"],
        hazard=None,
        golden_egg=None,
        power_egg=None,
        rescue=None,
        rescued=None,
        has_subtitle=False,
        has_thumbnail=False,
        duration_seconds=12.5,
        size_bytes=1024,
    )

    item = to_recorded_video_item(dto)

    assert item.match == dto.match
    assert item.rule == dto.rule
    assert item.stage == dto.stage
    assert item.gold_medals == dto.gold_medals
    assert item.silver_medals == dto.silver_medals
    assert item.allies == dto.allies
    assert item.enemies == dto.enemies


def test_recorded_video_dto_metadata_fields_match_schema() -> None:
    dto_fields = {field.name for field in dataclass_fields(RecordedVideoDTO)}
    non_metadata_fields = {
        "video_id",
        "path",
        "filename",
        "has_subtitle",
        "has_thumbnail",
        "duration_seconds",
        "size_bytes",
    }
    assert dto_fields - non_metadata_fields == (
        COMMON_METADATA_FIELDS
        | BATTLE_METADATA_FIELDS
        | SALMON_METADATA_FIELDS
    )
