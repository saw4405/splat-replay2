"""対戦履歴の同期サービス。"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from pathlib import Path

from splat_replay.application.interfaces import (
    BattleHistoryRecord,
    BattleHistoryRepositoryPort,
    ConfigPort,
    LoggerPort,
)
from splat_replay.domain.models import (
    BattleResult,
    GameMode,
    RecordingMetadata,
)

SCHEMA_VERSION = 1
UNKNOWN_WEAPON_LABEL = "不明"


class BattleHistoryService:
    """録画メタデータと独立履歴の同期を担当する。"""

    def __init__(
        self,
        repository: BattleHistoryRepositoryPort,
        config: ConfigPort,
        logger: LoggerPort,
        base_dir: Path,
    ) -> None:
        self._repository = repository
        self._config = config
        self._logger = logger
        self._base_dir = base_dir

    def sync_recording(
        self, video_path: Path, metadata: RecordingMetadata
    ) -> None:
        """録画メタデータを履歴へ同期する。"""
        if metadata.game_mode is not GameMode.BATTLE:
            return

        source_video_id = self._build_source_video_id(video_path)
        if source_video_id is None:
            return

        try:
            existing = self._repository.find_by_source_video_id(
                source_video_id
            )
            allow_create = (
                self._config.get_behavior_settings().record_battle_history
            )
            if existing is None and not allow_create:
                self._logger.info(
                    "対戦履歴の新規記録をスキップしました",
                    source_video_id=source_video_id,
                    reason="disabled",
                )
                return

            now = datetime.now()
            record = self._build_record(
                source_video_id=source_video_id,
                metadata=metadata,
                now=now,
            )
            if existing is not None:
                record = replace(
                    record,
                    created_at=existing.created_at,
                    updated_at=now,
                )

            self._repository.upsert(record)
            self._logger.info(
                "対戦履歴を同期しました",
                source_video_id=source_video_id,
                is_partial=record.is_partial,
                missing_fields=list(record.missing_fields),
            )
        except Exception as exc:
            self._logger.warning(
                "対戦履歴の同期に失敗しました",
                video_path=str(video_path),
                error=str(exc),
            )

    def _build_source_video_id(self, video_path: Path) -> str | None:
        base_dir = self._base_dir.resolve()
        resolved_video = video_path.resolve()
        try:
            return str(resolved_video.relative_to(base_dir).as_posix())
        except ValueError:
            self._logger.warning(
                "base_dir 配下ではないため対戦履歴の同期をスキップしました",
                video_path=str(video_path),
                base_dir=str(self._base_dir),
            )
            return None

    def _build_record(
        self,
        *,
        source_video_id: str,
        metadata: RecordingMetadata,
        now: datetime,
    ) -> BattleHistoryRecord:
        result = (
            metadata.result
            if isinstance(metadata.result, BattleResult)
            else None
        )
        missing_fields = _collect_missing_fields(metadata, result)

        return BattleHistoryRecord(
            schema_version=SCHEMA_VERSION,
            source_video_id=source_video_id,
            created_at=now,
            updated_at=now,
            game_mode=metadata.game_mode.name,
            started_at=metadata.started_at,
            rate=str(metadata.rate) if metadata.rate is not None else None,
            match=(
                result.match.name
                if result is not None and result.match is not None
                else None
            ),
            rule=(
                result.rule.name
                if result is not None and result.rule is not None
                else None
            ),
            stage=(
                result.stage.name
                if result is not None and result.stage is not None
                else None
            ),
            judgement=(
                metadata.judgement.name
                if metadata.judgement is not None
                else None
            ),
            kill=result.kill if result is not None else None,
            death=result.death if result is not None else None,
            special=result.special if result is not None else None,
            gold_medals=result.gold_medals if result is not None else None,
            silver_medals=result.silver_medals if result is not None else None,
            allies=metadata.allies,
            enemies=metadata.enemies,
            is_partial=bool(missing_fields),
            missing_fields=missing_fields,
        )


def _collect_missing_fields(
    metadata: RecordingMetadata,
    result: BattleResult | None,
) -> tuple[str, ...]:
    missing_fields: list[str] = []

    if result is None:
        missing_fields.extend(
            [
                "match",
                "rule",
                "stage",
                "kill",
                "death",
                "special",
                "gold_medals",
                "silver_medals",
            ]
        )
    else:
        for field_name in (
            "match",
            "rule",
            "stage",
            "kill",
            "death",
            "special",
            "gold_medals",
            "silver_medals",
        ):
            if getattr(result, field_name) is None:
                missing_fields.append(field_name)

    if metadata.judgement is None:
        missing_fields.append("judgement")

    if _weapon_slots_missing(metadata.allies):
        missing_fields.append("allies")
    if _weapon_slots_missing(metadata.enemies):
        missing_fields.append("enemies")

    return tuple(missing_fields)


def _weapon_slots_missing(
    slots: tuple[str, str, str, str] | None,
) -> bool:
    if slots is None:
        return True
    return any((not slot) or slot == UNKNOWN_WEAPON_LABEL for slot in slots)
