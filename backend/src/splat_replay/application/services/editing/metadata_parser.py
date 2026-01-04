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
    def parse_battle_result_updates(
        current: BattleResult, data: Mapping[str, object]
    ) -> BattleResult:
        """Parse updates for BattleResult from external data.

        Invalid values are silently ignored (lenient parsing).
        """
        updates = {}

        if "match" in data and isinstance(data["match"], str):
            try:
                updates["match"] = Match(data["match"])
            except Exception:
                pass

        if "rule" in data and isinstance(data["rule"], str):
            try:
                updates["rule"] = Rule(data["rule"])
            except Exception:
                pass

        if "stage" in data and isinstance(data["stage"], str):
            try:
                updates["stage"] = Stage(data["stage"])
            except Exception:
                pass

        for field in ("kill", "death", "special"):
            if field in data:
                try:
                    value = data[field]
                    if isinstance(value, int):
                        updates[field] = value
                    elif isinstance(value, str):
                        updates[field] = int(value)
                except Exception:
                    pass

        return replace(current, **updates) if updates else current

    @staticmethod
    def parse_salmon_result_updates(
        current: SalmonResult, data: Mapping[str, object]
    ) -> SalmonResult:
        """Parse updates for SalmonResult from external data.

        Invalid values are silently ignored (lenient parsing).
        """
        updates = {}

        if "stage" in data and isinstance(data["stage"], str):
            try:
                updates["stage"] = Stage[data["stage"]]
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
                    elif isinstance(value, str):
                        updates[field] = int(value)
                except Exception:
                    pass

        return replace(current, **updates) if updates else current

    @staticmethod
    def parse_metadata_updates(
        current: RecordingMetadata, data: Mapping[str, object]
    ) -> RecordingMetadata:
        """Parse updates for RecordingMetadata from external data.

        Invalid values are silently ignored (lenient parsing).
        Delegates result parsing to specialized methods.
        """
        updates = {}

        # game_mode
        if "game_mode" in data and isinstance(data["game_mode"], str):
            try:
                updates["game_mode"] = GameMode(data["game_mode"])
            except Exception:
                pass

        # started_at
        if "started_at" in data and isinstance(data["started_at"], str):
            try:
                updates["started_at"] = datetime.fromisoformat(
                    data["started_at"]
                )
            except Exception:
                pass

        # rate
        if "rate" in data and isinstance(data["rate"], str):
            try:
                updates["rate"] = RateBase.create(data["rate"])
            except Exception:
                pass

        # judgement
        if "judgement" in data and isinstance(data["judgement"], str):
            try:
                updates["judgement"] = Judgement(data["judgement"])
            except Exception:
                pass

        # result (delegate to specialized parsers)
        if current.result is not None:
            if isinstance(current.result, BattleResult):
                updates["result"] = MetadataParser.parse_battle_result_updates(
                    current.result, data
                )
            else:  # SalmonResult
                updates["result"] = MetadataParser.parse_salmon_result_updates(
                    current.result, data
                )

        return replace(current, **updates) if updates else current

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
            game_mode = GameMode(game_mode_raw)
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
                judgement = Judgement(judgement_raw)
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

        return RecordingMetadata(
            game_mode=game_mode,
            started_at=started_at,
            rate=rate,
            judgement=judgement,
            result=result,
        )
