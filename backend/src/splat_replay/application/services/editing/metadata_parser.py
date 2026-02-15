"""Metadata parsing service for updating domain models from external data.

This service handles the complex parsing logic that was previously in
domain models' with_updates() methods. Parsing is an application concern,
not a domain concern.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from typing import Mapping

from splat_replay.domain.models import (
    BattleResult,
    GameMode,
    Judgement,
    Match,
    RecordingMetadata,
    Rule,
    SalmonResult,
    Stage,
)
from splat_replay.domain.models.rate import RateBase


class MetadataParser:
    """Service for parsing and updating metadata from external sources."""

    @staticmethod
    def _parse_weapon_slots(
        value: object,
    ) -> tuple[str, str, str, str] | None:
        """ブキ4枠配列をパースする。"""
        if not isinstance(value, (list, tuple)):
            return None
        if len(value) != 4:
            return None
        # 型ナローイング: 全要素がstrであることを検証し、型システムに伝える
        if not all(isinstance(item, str) for item in value):
            return None
        # この時点でvalueは長さ4のlist[str] | tuple[str, ...]と推論される
        # assertで型チェッカーに各要素がstrであることを明示的に保証
        assert isinstance(value[0], str)
        assert isinstance(value[1], str)
        assert isinstance(value[2], str)
        assert isinstance(value[3], str)
        return (value[0], value[1], value[2], value[3])

    @staticmethod
    def _parse_battle_result_updates_with_applied_fields(
        current: BattleResult, data: Mapping[str, object]
    ) -> tuple[BattleResult, set[str]]:
        """BattleResult の更新をパースし、適用できたフィールドを返す。"""
        updates = {}
        applied_fields: set[str] = set()

        if "match" in data and isinstance(data["match"], str):
            try:
                updates["match"] = Match[data["match"]]
                applied_fields.add("match")
            except Exception:
                pass

        if "rule" in data and isinstance(data["rule"], str):
            try:
                updates["rule"] = Rule[data["rule"]]
                applied_fields.add("rule")
            except Exception:
                pass

        if "stage" in data and isinstance(data["stage"], str):
            try:
                updates["stage"] = Stage[data["stage"]]
                applied_fields.add("stage")
            except Exception:
                pass

        for field in ("kill", "death", "special"):
            if field in data:
                try:
                    value = data[field]
                    if isinstance(value, int):
                        updates[field] = value
                        applied_fields.add(field)
                    elif isinstance(value, str):
                        updates[field] = int(value)
                        applied_fields.add(field)
                except Exception:
                    pass

        updated = replace(current, **updates) if updates else current
        return updated, applied_fields

    @staticmethod
    def _parse_salmon_result_updates_with_applied_fields(
        current: SalmonResult, data: Mapping[str, object]
    ) -> tuple[SalmonResult, set[str]]:
        """SalmonResult の更新をパースし、適用できたフィールドを返す。"""
        updates = {}
        applied_fields: set[str] = set()

        if "stage" in data and isinstance(data["stage"], str):
            try:
                updates["stage"] = Stage[data["stage"]]
                applied_fields.add("stage")
            except Exception:
                pass

        for field in (
            "hazard",
            "golden_egg",
            "power_egg",
            "rescue",
            "rescued",
        ):
            if field in data:
                try:
                    value = data[field]
                    if isinstance(value, int):
                        updates[field] = value
                        applied_fields.add(field)
                    elif isinstance(value, str):
                        updates[field] = int(value)
                        applied_fields.add(field)
                except Exception:
                    pass

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
        current: RecordingMetadata, data: Mapping[str, object]
    ) -> tuple[RecordingMetadata, frozenset[str]]:
        """更新内容をパースし、適用できたフィールドを返す。"""
        updates: dict[str, object] = {}
        applied_fields: set[str] = set()

        # game_mode
        if "game_mode" in data and isinstance(data["game_mode"], str):
            try:
                updates["game_mode"] = GameMode[data["game_mode"]]
                applied_fields.add("game_mode")
            except Exception:
                pass

        # started_at
        if "started_at" in data and isinstance(data["started_at"], str):
            try:
                updates["started_at"] = datetime.fromisoformat(
                    data["started_at"]
                )
                applied_fields.add("started_at")
            except Exception:
                pass

        # rate
        if "rate" in data and isinstance(data["rate"], str):
            try:
                updates["rate"] = RateBase.create(data["rate"])
                applied_fields.add("rate")
            except Exception:
                pass

        # judgement
        if "judgement" in data and isinstance(data["judgement"], str):
            try:
                updates["judgement"] = Judgement[data["judgement"]]
                applied_fields.add("judgement")
            except Exception:
                pass

        # allies / enemies
        for field_name in ("allies", "enemies"):
            if field_name not in data:
                continue
            parsed_slots = MetadataParser._parse_weapon_slots(data[field_name])
            if parsed_slots is None:
                continue
            updates[field_name] = parsed_slots
            applied_fields.add(field_name)

        # result (delegate to specialized parsers)
        if current.result is not None:
            if isinstance(current.result, BattleResult):
                result, result_fields = (
                    MetadataParser._parse_battle_result_updates_with_applied_fields(
                        current.result, data
                    )
                )
            else:  # SalmonResult
                result, result_fields = (
                    MetadataParser._parse_salmon_result_updates_with_applied_fields(
                        current.result, data
                    )
                )
            updates["result"] = result
            applied_fields.update(result_fields)

        updated = replace(current, **updates) if updates else current
        return updated, frozenset(applied_fields)

    @staticmethod
    def parse_metadata_updates(
        current: RecordingMetadata, data: Mapping[str, object]
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
        if not isinstance(game_mode_raw, str):
            raise ValidationError(
                "game_mode is required and must be a string",
                error_code="METADATA_GAME_MODE_REQUIRED",
            )
        try:
            game_mode = GameMode[game_mode_raw]
        except Exception as e:
            raise ValidationError(
                f"Invalid game_mode value: {game_mode_raw}",
                error_code="METADATA_GAME_MODE_INVALID",
                cause=e,
            ) from e

        started_at_raw = data.get("started_at")
        started_at: datetime | None
        try:
            if isinstance(started_at_raw, str) and started_at_raw:
                started_at = datetime.fromisoformat(started_at_raw)
            else:
                started_at = None
        except Exception:
            # オプションフィールド: パース失敗は None として扱う
            started_at = None

        rate_raw = data.get("rate")
        rate: RateBase | None
        try:
            if isinstance(rate_raw, str) and rate_raw:
                rate = RateBase.create(rate_raw)
            else:
                rate = None
        except Exception:
            # オプションフィールド: パース失敗は None として扱う
            rate = None

        judgement_raw = data.get("judgement")
        judgement: Judgement | None
        try:
            if isinstance(judgement_raw, str) and judgement_raw:
                judgement = Judgement[judgement_raw]
            else:
                judgement = None
        except Exception:
            # オプションフィールド: パース失敗は None として扱う
            judgement = None

        # Result parsing - delegate to domain from_dict methods
        result: BattleResult | SalmonResult | None = None
        if game_mode == GameMode.BATTLE:
            from splat_replay.domain.models.recording_metadata import (
                BATTLE_RESULT_REQUIRED_FIELDS,
                has_required_fields,
            )

            if has_required_fields(data, BATTLE_RESULT_REQUIRED_FIELDS):
                try:
                    result = BattleResult.from_dict(data)
                except Exception:
                    # オプションフィールド: パース失敗は None として扱う
                    result = None
        elif game_mode == GameMode.SALMON:
            from splat_replay.domain.models.recording_metadata import (
                SALMON_RESULT_REQUIRED_FIELDS,
                has_required_fields,
            )

            if has_required_fields(data, SALMON_RESULT_REQUIRED_FIELDS):
                try:
                    result = SalmonResult.from_dict(data)
                except Exception:
                    # オプションフィールド: パース失敗は None として扱う
                    result = None

        allies = MetadataParser._parse_weapon_slots(data.get("allies"))
        enemies = MetadataParser._parse_weapon_slots(data.get("enemies"))

        return RecordingMetadata(
            game_mode=game_mode,
            started_at=started_at,
            rate=rate,
            judgement=judgement,
            allies=allies,
            enemies=enemies,
            result=result,
        )
