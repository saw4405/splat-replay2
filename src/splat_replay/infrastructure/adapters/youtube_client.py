"""YouTube API クライアント。"""

from __future__ import annotations

import gc
import pickle
from pathlib import Path
from typing import List, Optional, Union, cast

import google.auth.exceptions
from google.auth.external_account_authorized_user import (
    Credentials as Credentials1,
)
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials as Credentials2
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import Resource, build
from googleapiclient.http import MediaFileUpload
from structlog.stdlib import BoundLogger

from splat_replay.application.interfaces import (
    AuthenticatedClientPort,
    Caption,
    PrivacyStatus,
    UploadPort,
)
from splat_replay.shared import paths

Credentials = Union[
    Credentials1,
    Credentials2,
]


class YouTubeClient(UploadPort, AuthenticatedClientPort):
    """YouTube Data API を利用する。"""

    def __init__(self, logger: BoundLogger):
        self.logger = logger
        self.TOKEN_FILE = paths.config("token.pickle")
        self.CLIENT_SECRET_FILE = paths.config("client_secrets.json")
        self.API_NAME = "youtube"
        self.API_VERSION = "v3"
        self.SCOPES = [
            "https://www.googleapis.com/auth/youtube.upload",
            "https://www.googleapis.com/auth/youtube.force-ssl",
        ]

        self._credentials: Optional[Credentials] = None
        self._youtube: Optional[Resource] = None

    def _load_credentials(self) -> Optional[Credentials]:
        """認証情報をファイルからロードする

        Returns:
            Optional[Credentials]: 認証情報が存在する場合はCredentials、それ以外はNone
        """
        if not self.TOKEN_FILE.exists():
            return None

        with open(self.TOKEN_FILE, "rb") as token_file:
            data = pickle.load(token_file)
        return cast(Optional[Credentials], data)

    def _save_credentials(self, credentials: Credentials) -> None:
        """認証情報をファイルに保存する

        Args:
            credentials (Credentials): 保存する認証情報
        """
        with open(self.TOKEN_FILE, "wb") as token_file:
            pickle.dump(credentials, token_file)

    def _ensure_credentials_file(self) -> None:
        """認証情報ファイルの存在を確認する。"""
        if self.CLIENT_SECRET_FILE.exists():
            return

        message = (
            "YouTube API の認証情報ファイルが見つかりません。 "
            f"配置先: {self.CLIENT_SECRET_FILE}"
        )
        self.logger.error(message)
        raise FileNotFoundError(message)

    def _get_credentials(self) -> Credentials:
        """認証情報を取得する

        Returns:
            Credentials: 取得した認証情報
        """
        credentials = self._load_credentials()
        if credentials:
            try:
                if credentials.expired and credentials.refresh_token:
                    credentials.refresh(Request())
                    self._save_credentials(credentials)
                return credentials
            except Exception:
                # 認証更新できなかった場合は新規認証を行う
                pass

        self._ensure_credentials_file()

        flow = InstalledAppFlow.from_client_secrets_file(
            str(self.CLIENT_SECRET_FILE), self.SCOPES
        )
        credentials = cast(Credentials, flow.run_local_server(port=8080))
        self._save_credentials(credentials)
        return credentials

    def _ensure_credentials(self) -> None:
        """認証情報が有効であることを確認する"""
        needs_refresh = (
            self._credentials is None
            or self._credentials.expired
            or self._youtube is None
        )
        if not needs_refresh:
            return

        self._credentials = self._get_credentials()
        self._youtube = build(
            self.API_NAME,
            self.API_VERSION,
            credentials=self._credentials,
        )

    def authenticate(self) -> None:
        """認証を行う。"""
        self._ensure_credentials()
        self.logger.info("YouTube API 認証完了")

    def upload(
        self,
        path: Path,
        title: str,
        description: str,
        tags: List[str] = [],
        privacy_status: PrivacyStatus = "private",
        thumb: Optional[Path] = None,
        caption: Optional[Caption] = None,
        playlist_id: str = "",
    ) -> None:
        video_id = self.upload_video(
            path, title, description, tags, privacy_status=privacy_status
        )
        if not video_id:
            raise RuntimeError("動画のアップロードに失敗しました")
        self.logger.info("動画アップロード完了", video_id=video_id)

        if thumb:
            self.upload_thumbnail(video_id, thumb)
            self.logger.info("サムネイルアップロード完了", video_id=video_id)

        if caption:
            self.upload_subtitle(
                video_id,
                caption.subtitle,
                caption.caption_name,
                caption.language,
            )
            self.logger.info("字幕アップロード完了", video_id=video_id)

        if playlist_id:
            self.add_to_playlist(video_id, playlist_id)
            self.logger.info(
                "プレイリストに追加完了",
                video_id=video_id,
                playlist_id=playlist_id,
            )

    def upload_video(
        self,
        path: Path,
        title: str,
        description: str,
        tags: List[str] = [],
        category: int = 20,
        privacy_status: PrivacyStatus = "private",
    ) -> Optional[str]:
        """動画をアップロードし ID を返す。"""
        self.logger.info("動画アップロード実行", path=str(path))
        self._ensure_credentials()
        if self._youtube is None:
            raise RuntimeError("YouTube クライアントの初期化に失敗しました")

        media_file = None
        try:
            media_file = MediaFileUpload(
                path, mimetype="video/*", resumable=True
            )
            request = self._youtube.videos().insert(
                part="snippet,status",
                body={
                    "snippet": {
                        "title": title,
                        "description": description,
                        "tags": tags,
                        "categoryId": category,
                    },
                    "status": {"privacyStatus": privacy_status},
                },
                media_body=media_file,
            )
            response = request.execute()
            response_id = (
                response.get("id") if isinstance(response, dict) else None
            )
            return cast(Optional[str], response_id)

        except google.auth.exceptions.GoogleAuthError as e:
            self.logger.error(f"認証に失敗しました: {e}")
            return None
        except Exception as e:
            self.logger.error(f"アップロードに失敗しました: {e}")
            return None
        finally:
            if media_file:
                del media_file
                gc.collect()

    def upload_thumbnail(self, video_id: str, thumb: Path) -> None:
        """サムネイルをアップロードする。"""
        self.logger.info(
            "サムネイルアップロード実行", video_id=video_id, thumb=str(thumb)
        )
        self._ensure_credentials()
        if self._youtube is None:
            raise RuntimeError("YouTube クライアントの初期化に失敗しました")

        media_file = None
        try:
            media_file = MediaFileUpload(thumb)
            request = self._youtube.thumbnails().set(
                videoId=video_id, media_body=media_file
            )
            request.execute()
            return

        except google.auth.exceptions.GoogleAuthError as e:
            self.logger.error(f"認証に失敗しました: {e}")
        except Exception as e:
            self.logger.error(f"アップロードに失敗しました: {e}")
        finally:
            if media_file:
                del media_file
                gc.collect()

    def upload_subtitle(
        self,
        video_id: str,
        subtitle: Path,
        caption_name: str,
        language: str = "ja",
    ) -> None:
        """字幕ファイルをアップロードする。"""
        self.logger.info(
            "字幕アップロード実行", video_id=video_id, subtitle=str(subtitle)
        )
        self._ensure_credentials()
        if self._youtube is None:
            raise RuntimeError("YouTube クライアントの初期化に失敗しました")

        media_file = None
        try:
            media_file = MediaFileUpload(subtitle)
            request = self._youtube.captions().insert(
                part="snippet",
                body={
                    "snippet": {
                        "videoId": video_id,
                        "language": language,
                        "name": caption_name,
                    }
                },
                media_body=media_file,
            )
            request.execute()
            return

        except google.auth.exceptions.GoogleAuthError as e:
            self.logger.error(f"認証に失敗しました: {e}")
        except Exception as e:
            self.logger.error(f"アップロードに失敗しました: {e}")
        finally:
            if media_file:
                del media_file
                gc.collect()

    def add_to_playlist(self, video_id: str, playlist_id: str) -> None:
        """動画をプレイリストに追加する。"""
        self.logger.info(
            "プレイリスト追加実行", video_id=video_id, playlist_id=playlist_id
        )
        self._ensure_credentials()
        if self._youtube is None:
            raise RuntimeError("YouTube クライアントの初期化に失敗しました")

        try:
            request = self._youtube.playlistItems().insert(
                part="snippet",
                body={
                    "snippet": {
                        "playlistId": playlist_id,
                        "resourceId": {
                            "kind": "youtube#video",
                            "videoId": video_id,
                        },
                    }
                },
            )
            request.execute()
            return

        except google.auth.exceptions.GoogleAuthError as e:
            self.logger.error(f"認証に失敗しました: {e}")
        except Exception as e:
            self.logger.error(f"アップロードに失敗しました: {e}")
