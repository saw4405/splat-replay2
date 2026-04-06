"""対戦履歴の同期サービス。"""

from __future__ import annotations

from pathlib import Path

from splat_replay.application.interfaces import (
    BattleHistoryEntry,
    BattleHistoryRepositoryPort,
    ConfigPort,
    LoggerPort,
)
from splat_replay.domain.models import (
    GameMode,
    RecordingMetadata,
)


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

            self._repository.upsert(
                BattleHistoryEntry(
                    source_video_id=source_video_id,
                    metadata=metadata,
                )
            )
            self._logger.info(
                "対戦履歴を同期しました",
                source_video_id=source_video_id,
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
