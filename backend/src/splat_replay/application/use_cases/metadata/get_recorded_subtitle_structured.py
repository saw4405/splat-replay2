"""録画字幕取得ユースケース（構造化データ版）。"""

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


class GetRecordedSubtitleStructuredUseCase:
    """録画の字幕を構造化データとして取得するユースケース。

    責務：
    - 録画ファイルに関連付けられた字幕（.srt）を取得
    - SRT形式から構造化データ（SubtitleDataDTO）に変換
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

    async def execute(self, video_id: str) -> SubtitleDataDTO:
        """録画字幕を構造化データとして取得。

        Args:
            video_id: 取得する動画の ID（runtime_root からの相対パス）

        Returns:
            SubtitleDataDTO: 字幕の構造化データ

        Raises:
            FileNotFoundError: 指定された動画が存在しない場合
            ValueError: 字幕のパースに失敗した場合
        """
        video_path = self._runtime_root / video_id

        if not video_path.exists():
            self._logger.warning(
                f"取得対象の録画ファイルが見つかりません: {video_path}"
            )
            raise FileNotFoundError(
                f"録画ファイルが見つかりません: {video_id}"
            )

        subtitle_content = self._repository.get_subtitle(video_path)

        if subtitle_content is None or not subtitle_content.strip():
            self._logger.info(f"字幕ファイルが存在しません: {video_path}")
            return SubtitleDataDTO(blocks=[])

        # SRT形式から構造化データに変換
        try:
            blocks = self._converter.from_srt(subtitle_content)
            return SubtitleDataDTO(blocks=blocks)
        except ValueError as e:
            self._logger.error(f"字幕のパースに失敗しました: {e}")
            raise
