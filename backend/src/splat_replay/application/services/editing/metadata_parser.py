"""Metadata parsing service for updating domain models from external data.

This service handles the complex parsing logic that was previously in
domain models' with_updates() methods. Parsing is an application concern,
not a domain concern.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from typing import Mapping, cast

from splat_replay.application.metadata import (
    BATTLE_METADATA_FIELD_DEFINITIONS,
    COMMON_METADATA_FIELD_DEFINITIONS,
    SALMON_METADATA_FIELD_DEFINITIONS,
    SALMON_RESULT_REQUIRED_FIELDS,
    has_required_fields,
)
from splat_replay.application.metadata.codec import (
    MISSING,
    parse_metadata_field_update,
    parse_optional_metadata_field,
)
from splat_replay.domain.models import (
    BattleResult,
    GameMode,
    Judgement,
    RecordingMetadata,
    SalmonResult,
)
from splat_replay.domain.models.rate import RateBase


class MetadataParser:
    """Service for parsing and updating metadata from external sources."""

    @staticmethod
    def _is_clearable_common_field(field_key: str, raw: object) -> bool:
        """common field に対する明示的なクリア指定かどうかを返す。"""
        return field_key in {"started_at", "rate", "judgement"} and raw in {
            None,
            "",
        }

    @staticmethod
    def _is_clearable_battle_result_field(field_key: str, raw: object) -> bool:
        """BattleResult の enum 項目への明示的なクリア指定かどうかを返す。"""
        return field_key in {"match", "rule", "stage"} and raw in {
            None,
            "",
        }

    @staticmethod
    def _parse_battle_result_updates_with_applied_fields(
        current: BattleResult, data: Mapping[str, object]
    ) -> tuple[BattleResult, set[str]]:
        """BattleResult の更新をパースし、適用できたフィールドを返す。"""
        updates: dict[str, object] = {}
        applied_fields: set[str] = set()

        for field in BATTLE_METADATA_FIELD_DEFINITIONS:
            if field.key not in data:
                continue
            raw = data[field.key]
            if MetadataParser._is_clearable_battle_result_field(
                field.key, raw
            ):
                updates[field.attr_name] = None
                applied_fields.add(field.key)
                continue
            parsed = parse_metadata_field_update(field, raw)
            if parsed is MISSING:
                continue
            updates[field.attr_name] = parsed
            applied_fields.add(field.key)

        updated = replace(current, **updates) if updates else current
        return updated, applied_fields

    @staticmethod
    def _parse_salmon_result_updates_with_applied_fields(
        current: SalmonResult, data: Mapping[str, object]
    ) -> tuple[SalmonResult, set[str]]:
        """SalmonResult の更新をパースし、適用できたフィールドを返す。"""
        updates: dict[str, object] = {}
        applied_fields: set[str] = set()

        for field in SALMON_METADATA_FIELD_DEFINITIONS:
            if field.key not in data:
                continue
            parsed = parse_metadata_field_update(field, data[field.key])
            if parsed is MISSING:
                continue
            updates[field.attr_name] = parsed
            applied_fields.add(field.key)

        updated = replace(current, **updates) if updates else current
        return updated, applied_fields

    @staticmethod
    def parse_battle_result_updates(
        current: BattleResult, data: Mapping[str, object]
    ) -> BattleResult:
        """Parse updates for BattleResult from external data.

        Invalid values are silently ignored (lenient parsing).
        """
        updated, _ = (
            MetadataParser._parse_battle_result_updates_with_applied_fields(
                current, data
            )
        )
        return updated

    @staticmethod
    def parse_salmon_result_updates(
        current: SalmonResult, data: Mapping[str, object]
    ) -> SalmonResult:
        """Parse updates for SalmonResult from external data.

        Invalid values are silently ignored (lenient parsing).
        """
        updated, _ = (
            MetadataParser._parse_salmon_result_updates_with_applied_fields(
                current, data
            )
        )
        return updated

    @staticmethod
    def parse_metadata_updates_with_applied_fields(
        current: RecordingMetadata,
        data: Mapping[str, object],
    ) -> tuple[RecordingMetadata, frozenset[str]]:
        """更新内容をパースし、適用できたフィールドを返す。"""
        updates: dict[str, object] = {}
        applied_fields: set[str] = set()

        for field in COMMON_METADATA_FIELD_DEFINITIONS:
            if field.key not in data:
                continue
            raw = data[field.key]
            if MetadataParser._is_clearable_common_field(field.key, raw):
                updates[field.attr_name] = None
                applied_fields.add(field.key)
                continue
            parsed = parse_metadata_field_update(field, raw)
            if parsed is MISSING:
                continue
            updates[field.attr_name] = parsed
            applied_fields.add(field.key)

        next_game_mode = cast(
            GameMode, updates.get("game_mode", current.game_mode)
        )
        current_result = current.result
        if (
            isinstance(current_result, BattleResult)
            and next_game_mode == GameMode.SALMON
        ) or (
            isinstance(current_result, SalmonResult)
            and next_game_mode == GameMode.BATTLE
        ):
            current_result = None
            updates["result"] = None

        # result (delegate to specialized parsers)
        if current_result is not None:
            if isinstance(current_result, BattleResult):
                result, result_fields = (
                    MetadataParser._parse_battle_result_updates_with_applied_fields(
                        current_result, data
                    )
                )
            else:  # SalmonResult
                result, result_fields = (
                    MetadataParser._parse_salmon_result_updates_with_applied_fields(
                        current_result, data
                    )
                )
            updates["result"] = result
            applied_fields.update(result_fields)

        updated = replace(current, **updates) if updates else current
        return updated, frozenset(applied_fields)

    @staticmethod
    def parse_metadata_updates(
        current: RecordingMetadata,
        data: Mapping[str, object],
    ) -> RecordingMetadata:
        """Parse updates for RecordingMetadata from external data.

        Invalid values are silently ignored (lenient parsing).
        Delegates result parsing to specialized methods.
        """
        updated, _ = MetadataParser.parse_metadata_updates_with_applied_fields(
            current, data
        )
        return updated

    @staticmethod
    def from_dict(data: Mapping[str, object]) -> RecordingMetadata:
        """Rehydrate metadata from persisted data.

        Application-layer parsing logic for external data sources.
        必須フィールドのパース失敗時は ValidationError を投げる。
        オプションフィールドのパース失敗時は None として扱う。
        """
        from splat_replay.domain.exceptions import ValidationError

        game_mode_raw = data.get("game_mode")
        game_mode_field = COMMON_METADATA_FIELD_DEFINITIONS[0]
        if not isinstance(game_mode_raw, str):
            raise ValidationError(
                "game_mode is required and must be a string",
                error_code="METADATA_GAME_MODE_REQUIRED",
            )
        parsed_game_mode = parse_metadata_field_update(
            game_mode_field, game_mode_raw
        )
        if parsed_game_mode is MISSING:
            raise ValidationError(
                f"Invalid game_mode value: {game_mode_raw}",
                error_code="METADATA_GAME_MODE_INVALID",
            )
        game_mode = cast(GameMode, parsed_game_mode)

        common_values: dict[str, object | None] = {}
        for field in COMMON_METADATA_FIELD_DEFINITIONS:
            if field.key == "game_mode":
                common_values[field.attr_name] = game_mode
                continue
            common_values[field.attr_name] = parse_optional_metadata_field(
                field, data.get(field.key)
            )

        result: BattleResult | SalmonResult | None = None
        if game_mode == GameMode.BATTLE:
            if any(
                field.key in data
                for field in BATTLE_METADATA_FIELD_DEFINITIONS
            ):
                try:
                    result = BattleResult.from_dict(data)
                except Exception:
                    result = None
        elif game_mode == GameMode.SALMON:
            if has_required_fields(data, SALMON_RESULT_REQUIRED_FIELDS):
                try:
                    result = SalmonResult.from_dict(data)
                except Exception:
                    result = None

        return RecordingMetadata(
            game_mode=game_mode,
            started_at=cast(datetime | None, common_values["started_at"]),
            rate=cast(RateBase | None, common_values["rate"]),
            judgement=cast(Judgement | None, common_values["judgement"]),
            allies=cast(
                tuple[str, str, str, str] | None, common_values["allies"]
            ),
            enemies=cast(
                tuple[str, str, str, str] | None, common_values["enemies"]
            ),
            result=result,
        )
