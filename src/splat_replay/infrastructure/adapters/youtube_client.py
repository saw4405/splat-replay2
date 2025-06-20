"""YouTube API クライアント。"""

from __future__ import annotations

from pathlib import Path


class YouTubeClient:
    """YouTube Data API を利用する。"""

    def upload(self, path: Path) -> str:
        """動画をアップロードし ID を返す。"""
        raise NotImplementedError

    def upload_thumbnail(self, video_id: str, thumb: Path) -> None:
        """サムネイルをアップロードする。"""
        raise NotImplementedError

    def upload_subtitle(self, video_id: str, subtitle: Path) -> None:
        """字幕ファイルをアップロードする。"""
        raise NotImplementedError

    def add_to_playlist(self, video_id: str, playlist_id: str) -> None:
        """動画をプレイリストに追加する。"""
        raise NotImplementedError
