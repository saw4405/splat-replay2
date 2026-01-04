"""録画字幕更新ユースケース（構造化データ版）。"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from splat_replay.application.dto import SubtitleDataDTO
from splat_replay.application.services.common import SubtitleConverter

if TYPE_CHECKING:
    from splat_replay.application.interfaces import (
        LoggerPort,
        VideoAssetRepositoryPort,
    )


class UpdateRecordedSubtitleStructuredUseCase:
    """録画の字幕を構造化データから更新するユースケース。

    責務：
    - 構造化データ（SubtitleDataDTO）をSRT形式に変換
    - 録画ファイルに字幕を保存
    """

    def __init__(
        self,
        repository: VideoAssetRepositoryPort,
        logger: LoggerPort,
        runtime_root: Path,
        converter: SubtitleConverter,
    ) -> None:
        self._repository = repository
        self._logger = logger
        self._runtime_root = runtime_root
        self._converter = converter

    async def execute(
        self, video_id: str, subtitle_data: SubtitleDataDTO
    ) -> None:
        """録画字幕を構造化データから更新。

        Args:
            video_id: 更新する動画の ID（runtime_root からの相対パス）
            subtitle_data: 字幕の構造化データ

        Raises:
            FileNotFoundError: 指定された動画が存在しない場合
        """
        video_path = self._runtime_root / video_id

        if not video_path.exists():
            self._logger.warning(
                f"更新対象の録画ファイルが見つかりません: {video_path}"
            )
            raise FileNotFoundError(
                f"録画ファイルが見つかりません: {video_id}"
            )

        # 構造化データをSRT形式に変換
        srt_content = self._converter.to_srt(subtitle_data.blocks)

        # 字幕を保存
        self._repository.save_subtitle(video_path, srt_content)
        self._logger.info(f"字幕を更新しました: {video_path}")
