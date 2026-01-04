"""編集済みビデオ削除ユースケース。"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from splat_replay.application.interfaces import (
        LoggerPort,
        VideoAssetRepositoryPort,
    )


class DeleteEditedVideoUseCase:
    """編集済みビデオを削除するユースケース。

    責務：
    - 編集済みファイル本体を削除
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
        """編集済みビデオを削除。

        Args:
            video_id: 削除する動画の ID（runtime_root からの相対パス）

        Raises:
            FileNotFoundError: 指定された動画が存在しない場合
        """
        video_path = self._runtime_root / video_id

        if not video_path.exists():
            self._logger.warning(
                f"削除対象の編集済みファイルが見つかりません: {video_path}"
            )
            raise FileNotFoundError(
                f"編集済みファイルが見つかりません: {video_id}"
            )

        success = self._repository.delete_edited(video_path)
        if not success:
            self._logger.error(
                f"編集済みファイルの削除に失敗しました: {video_path}"
            )
            raise RuntimeError(
                f"編集済みファイルの削除に失敗しました: {video_id}"
            )

        self._logger.info(f"編集済みファイルを削除しました: {video_path}")
