"""対戦履歴リポジトリ実装。"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from structlog.stdlib import BoundLogger

from splat_replay.application.interfaces import (
    BattleHistoryEntry,
    BattleHistoryRepositoryPort,
)
from splat_replay.application.metadata import recording_metadata_to_dict
from splat_replay.application.services.editing.metadata_parser import (
    MetadataParser,
)
from splat_replay.domain.config import VideoStorageSettings
from splat_replay.domain.models import RecordingMetadata


def _record_filename(source_video_id: str) -> str:
    """source_video_id からレコード JSON のファイル名を導出する。

    例: "recorded/20260405_233135_Xマッチ_LOSE_ザトウ.mkv"
        → "20260405_233135_Xマッチ_LOSE_ザトウ.json"
    """
    return Path(source_video_id).stem + ".json"


class FileBattleHistoryRepository(BattleHistoryRepositoryPort):
    """試合ごとの個別 JSON ファイルへ対戦履歴を保存する実装。

    フォーマットは動画サイドカーと同じ（recording_metadata_to_dict）。
    history_dir/
        20260405_233135_....json   ← 1 試合 = 1 ファイル
    """

    def __init__(
        self,
        settings: VideoStorageSettings,
        logger: BoundLogger,
        history_dir: Path | None = None,
    ) -> None:
        self._history_dir = history_dir or settings.history_dir
        self._logger = logger

    def _record_path(self, source_video_id: str) -> Path:
        return self._history_dir / _record_filename(source_video_id)

    def find_by_source_video_id(
        self, source_video_id: str
    ) -> BattleHistoryEntry | None:
        path = self._record_path(source_video_id)
        if not path.exists():
            return None
        metadata = self._load_metadata(path)
        if metadata is None:
            return None
        return BattleHistoryEntry(
            source_video_id=source_video_id, metadata=metadata
        )

    def list_all(self) -> list[BattleHistoryEntry]:
        """全履歴を取得する。"""
        if not self._history_dir.exists():
            return []

        entries: list[BattleHistoryEntry] = []
        for path in sorted(self._history_dir.glob("*.json")):
            try:
                metadata = self._load_metadata(path)
                if metadata is None:
                    continue
                # ファイル名 stem から source_video_id を復元できないため
                # recorded/ プレフィックスを付加する（推定）
                source_video_id = "recorded/" + path.stem
                entries.append(
                    BattleHistoryEntry(
                        source_video_id=source_video_id, metadata=metadata
                    )
                )
            except Exception as exc:
                self._logger.warning(
                    "対戦履歴ファイルの読み込みに失敗しました",
                    path=str(path),
                    error=str(exc),
                )
        return entries

    def upsert(self, entry: BattleHistoryEntry) -> None:
        self._history_dir.mkdir(parents=True, exist_ok=True)
        path = self._record_path(entry.source_video_id)
        payload = recording_metadata_to_dict(entry.metadata)

        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=self._history_dir,
            prefix=path.stem,
            suffix=".tmp",
            delete=False,
        ) as handle:
            temp_path = Path(handle.name)
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.flush()

        temp_path.replace(path)
        self._logger.info(
            "対戦履歴ファイルを保存しました",
            path=str(path),
        )

    def _load_metadata(self, path: Path) -> RecordingMetadata | None:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return None
            return MetadataParser.from_dict(data)
        except Exception as exc:
            self._logger.warning(
                "対戦履歴ファイルの解析に失敗しました",
                path=str(path),
                error=str(exc),
            )
            return None
