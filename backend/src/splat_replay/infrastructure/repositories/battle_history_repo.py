"""対戦履歴リポジトリ実装。"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from structlog.stdlib import BoundLogger

from splat_replay.application.interfaces import (
    BattleHistoryRecord,
    BattleHistoryRepositoryPort,
)
from splat_replay.domain.config import VideoStorageSettings

FILE_VERSION = 1


class FileBattleHistoryRepository(BattleHistoryRepositoryPort):
    """JSON ファイルへ対戦履歴を保存する実装。"""

    def __init__(
        self,
        settings: VideoStorageSettings,
        logger: BoundLogger,
        history_file: Path | None = None,
    ) -> None:
        self._history_file = history_file or settings.battle_history_file
        self._logger = logger

    def find_by_source_video_id(
        self, source_video_id: str
    ) -> BattleHistoryRecord | None:
        records = self._load_records()
        for record in records:
            if record.source_video_id == source_video_id:
                return record
        return None

    def upsert(self, record: BattleHistoryRecord) -> None:
        records = self._load_records()
        updated_records: list[BattleHistoryRecord] = []
        replaced = False
        for current in records:
            if current.source_video_id == record.source_video_id:
                updated_records.append(record)
                replaced = True
                continue
            updated_records.append(current)

        if not replaced:
            updated_records.append(record)

        self._write_records(updated_records)

    def _load_records(self) -> list[BattleHistoryRecord]:
        if not self._history_file.exists():
            return []

        payload = json.loads(self._history_file.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("対戦履歴ファイル形式が不正です。")
        version = payload.get("version", FILE_VERSION)
        if not isinstance(version, int) or version != FILE_VERSION:
            raise ValueError(f"未対応の対戦履歴バージョンです: {version!r}")

        raw_records = payload.get("records", [])
        if not isinstance(raw_records, list):
            raise ValueError("records の形式が不正です。")

        records: list[BattleHistoryRecord] = []
        for raw_record in raw_records:
            if not isinstance(raw_record, dict):
                raise ValueError("record の形式が不正です。")
            records.append(BattleHistoryRecord.from_dict(raw_record))
        return records

    def _write_records(self, records: list[BattleHistoryRecord]) -> None:
        self._history_file.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": FILE_VERSION,
            "records": [record.to_dict() for record in records],
        }

        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=self._history_file.parent,
            prefix=self._history_file.stem,
            suffix=".tmp",
            delete=False,
        ) as handle:
            temp_path = Path(handle.name)
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.flush()

        temp_path.replace(self._history_file)
        self._logger.info(
            "対戦履歴ファイルを保存しました",
            path=str(self._history_file),
            record_count=len(records),
        )
