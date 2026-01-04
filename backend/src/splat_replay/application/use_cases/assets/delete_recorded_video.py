"""録画済みビデオ削除ユースケース。"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from splat_replay.application.interfaces import (
        LoggerPort,
        VideoAssetRepositoryPort,
    )


class DeleteRecordedVideoUseCase:
    """録画済みビデオを削除するユースケース。

    責務：
    - 録画ファイル本体を削除
    - 関連ファイル（字幕・サムネイル・メタデータ）を削除
    """

    def __init__(
        self,
        repository: VideoAssetRepositoryPort,
        logger: LoggerPort,
        runtime_root: Path,
    ) -> None:
        self._repository = repository
        self._logger = logger
        self._runtime_root = runtime_root

    async def execute(self, video_id: str) -> None:
        """録画済みビデオを削除。

        Args:
            video_id: 削除する動画の ID（runtime_root からの相対パス）

        Raises:
            FileNotFoundError: 指定された動画が存在しない場合
        """
        video_path = self._runtime_root / video_id

        if not video_path.exists():
            self._logger.warning(
                f"削除対象の録画ファイルが見つかりません: {video_path}"
            )
            raise FileNotFoundError(
                f"録画ファイルが見つかりません: {video_id}"
            )

        success = self._repository.delete_recording(video_path)
        if not success:
            self._logger.error(
                f"録画ファイルの削除に失敗しました: {video_path}"
            )
            raise RuntimeError(f"録画ファイルの削除に失敗しました: {video_id}")

        self._logger.info(f"録画ファイルを削除しました: {video_path}")
