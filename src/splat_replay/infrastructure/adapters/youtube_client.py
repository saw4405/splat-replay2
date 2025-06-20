"""YouTube API クライアント。"""

from __future__ import annotations

from pathlib import Path

from splat_replay.shared.logger import get_logger

logger = get_logger()


class YouTubeClient:
    """YouTube Data API を利用する。"""

    def upload(self, path: Path) -> str:
        """動画をアップロードし ID を返す。"""
        logger.info("動画アップロード実行", path=str(path))
        raise NotImplementedError

    def upload_thumbnail(self, video_id: str, thumb: Path) -> None:
        """サムネイルをアップロードする。"""
        logger.info(
            "サムネイルアップロード実行", video_id=video_id, thumb=str(thumb)
        )
        raise NotImplementedError

    def upload_subtitle(self, video_id: str, subtitle: Path) -> None:
        """字幕ファイルをアップロードする。"""
        logger.info(
            "字幕アップロード実行", video_id=video_id, subtitle=str(subtitle)
        )
        raise NotImplementedError

    def add_to_playlist(self, video_id: str, playlist_id: str) -> None:
        """動画をプレイリストに追加する。"""
        logger.info(
            "プレイリスト追加実行", video_id=video_id, playlist_id=playlist_id
        )
        raise NotImplementedError
