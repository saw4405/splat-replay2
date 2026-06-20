"""YouTubeClient のテスト。

責務：
- YouTube API 統合の検証
- 認証フローの検証
- アップロード処理の検証（モック使用）
- エラーハンドリング

分類: logic

注意: 実際の YouTube API は呼び出さず、Mock/Stub で検証する。
"""

from pathlib import Path
from unittest.mock import MagicMock, Mock, mock_open, patch

import pytest
from google.oauth2.credentials import Credentials

from splat_replay.domain.exceptions import (
    ConfigurationError,
    ResourceNotFoundError,
)
from splat_replay.infrastructure.adapters.upload.youtube_client import (
    YouTubeClient,
)


@pytest.fixture
def mock_logger():
    """LoggerPortのモック。"""
    return MagicMock()


@pytest.fixture
def youtube_client(mock_logger):
    """YouTubeClientのインスタンス。"""
    return YouTubeClient(logger=mock_logger)


@pytest.fixture
def mock_credentials():
    """モックの認証情報。"""
    mock = Mock(spec=Credentials)
    mock.expired = False
    mock.refresh_token = "mock_refresh_token"
    return mock


class TestYouTubeClientAuthentication:
    """認証テスト。"""

    def test_ensure_credentials_file_raises_error_when_missing(
        self, youtube_client
    ):
        """CLIENT_SECRET_FILE が存在しない場合、エラーを発生させる。"""
        with patch("pathlib.Path.exists", return_value=False):
            with pytest.raises(
                ConfigurationError, match="認証情報ファイルが見つかりません"
            ):
                youtube_client._ensure_credentials_file()

    def test_load_credentials_returns_none_when_file_missing(
        self, youtube_client
    ):
        """TOKEN_FILE が存在しない場合、None を返す。"""
        with patch("pathlib.Path.exists", return_value=False):
            result = youtube_client._load_credentials()

            assert result is None

    def test_save_credentials_writes_to_file(
        self, youtube_client, mock_credentials
    ):
        """認証情報をファイルに保存する。"""
        with patch("builtins.open", mock_open()):
            with patch("pickle.dump") as mock_dump:
                youtube_client._save_credentials(mock_credentials)

                mock_dump.assert_called_once()
                assert mock_dump.call_args[0][0] == mock_credentials

    @patch(
        "splat_replay.infrastructure.adapters.upload.youtube_client.InstalledAppFlow"
    )
    def test_authenticate_with_new_credentials(
        self, mock_flow, youtube_client, mock_credentials
    ):
        """新規認証フロー（認証情報がない場合）。"""
        # Path.exists のモック
        with patch("pathlib.Path.exists", side_effect=[False, True]):
            # Flow のモック設定
            mock_flow_instance = MagicMock()
            mock_flow_instance.run_local_server.return_value = mock_credentials
            mock_flow.from_client_secrets_file.return_value = (
                mock_flow_instance
            )

            # discovery.build のモック
            with patch(
                "splat_replay.infrastructure.adapters.upload.youtube_client.discovery.build"
            ) as mock_build:
                mock_youtube = MagicMock()
                mock_build.return_value = mock_youtube

                # _save_credentials のモック
                with patch.object(
                    youtube_client, "_save_credentials"
                ) as mock_save:
                    youtube_client.authenticate()

                    # 新規認証フローが実行される
                    mock_flow_instance.run_local_server.assert_called_once()

                    # 認証情報が保存される
                    mock_save.assert_called()


class TestYouTubeClientUpload:
    """アップロードテスト。"""

    @patch(
        "splat_replay.infrastructure.adapters.upload.youtube_client.MediaFileUpload"
    )
    def test_upload_video_success(
        self, mock_media_upload, youtube_client, mock_credentials
    ):
        """動画アップロードが成功する。"""
        # 認証情報とYouTubeクライアントのモック
        youtube_client._credentials = mock_credentials
        mock_youtube = MagicMock()
        youtube_client._youtube = mock_youtube

        # アップロードレスポンスのモック
        mock_request = MagicMock()
        mock_request.execute.return_value = {"id": "video123"}
        mock_youtube.videos().insert.return_value = mock_request

        # テスト実行
        video_path = Path("/fake/path/to/video.mp4")
        video_id = youtube_client.upload_video(
            path=video_path,
            title="Test Video",
            description="Test Description",
            tags=["test"],
            privacy_status="private",
        )

        # 検証
        assert video_id == "video123"
        mock_youtube.videos().insert.assert_called_once()

    @patch(
        "splat_replay.infrastructure.adapters.upload.youtube_client.MediaFileUpload"
    )
    def test_upload_video_authentication_failure(
        self, mock_media_upload, youtube_client, mock_credentials, mock_logger
    ):
        """認証失敗時の動作。"""
        from google.auth.exceptions import GoogleAuthError

        # 認証情報とYouTubeクライアントのモック
        youtube_client._credentials = mock_credentials
        mock_youtube = MagicMock()
        youtube_client._youtube = mock_youtube

        # アップロードで認証エラーを発生
        mock_request = MagicMock()
        mock_request.execute.side_effect = GoogleAuthError("Auth failed")
        mock_youtube.videos().insert.return_value = mock_request

        # テスト実行
        video_path = Path("/fake/path/to/video.mp4")
        video_id = youtube_client.upload_video(
            path=video_path,
            title="Test Video",
            description="Test Description",
        )

        # 検証
        assert video_id is None
        # エラーログが記録される
        mock_logger.error.assert_called()

    @patch(
        "splat_replay.infrastructure.adapters.upload.youtube_client.MediaFileUpload"
    )
    def test_upload_thumbnail_success(
        self, mock_media_upload, youtube_client, mock_credentials
    ):
        """サムネイルアップロードが成功する。"""
        # 認証情報とYouTubeクライアントのモック
        youtube_client._credentials = mock_credentials
        mock_youtube = MagicMock()
        youtube_client._youtube = mock_youtube

        # サムネイルアップロードのモック
        mock_request = MagicMock()
        mock_youtube.thumbnails().set.return_value = mock_request

        # テスト実行
        thumb_path = Path("/fake/path/to/thumbnail.jpg")
        youtube_client.upload_thumbnail("video123", thumb_path)

        # 検証
        mock_youtube.thumbnails().set.assert_called_once()

    @patch(
        "splat_replay.infrastructure.adapters.upload.youtube_client.MediaFileUpload"
    )
    def test_upload_subtitle_success(
        self, mock_media_upload, youtube_client, mock_credentials
    ):
        """字幕アップロードが成功する。"""
        # 認証情報とYouTubeクライアントのモック
        youtube_client._credentials = mock_credentials
        mock_youtube = MagicMock()
        youtube_client._youtube = mock_youtube

        # 字幕アップロードのモック
        mock_request = MagicMock()
        mock_youtube.captions().insert.return_value = mock_request

        # テスト実行
        subtitle_path = Path("/fake/path/to/subtitle.srt")
        youtube_client.upload_subtitle(
            "video123", subtitle_path, "Test Caption", "ja"
        )

        # 検証
        mock_youtube.captions().insert.assert_called_once()


class TestYouTubeClientIntegration:
    """統合テスト（upload メソッド）。"""

    @patch.object(YouTubeClient, "upload_video")
    @patch.object(YouTubeClient, "upload_thumbnail")
    @patch.object(YouTubeClient, "upload_subtitle")
    @patch.object(YouTubeClient, "add_to_playlist")
    def test_upload_with_all_options(
        self,
        mock_add_playlist,
        mock_upload_subtitle,
        mock_upload_thumbnail,
        mock_upload_video,
        youtube_client,
    ):
        """全オプション付きアップロード。"""
        from splat_replay.application.interfaces import Caption

        # upload_video のモック戻り値
        mock_upload_video.return_value = "video123"

        # テスト実行
        video_path = Path("/fake/path/to/video.mp4")
        thumb_path = Path("/fake/path/to/thumb.jpg")
        subtitle_path = Path("/fake/path/to/subtitle.srt")
        caption = Caption(
            subtitle=subtitle_path,
            caption_name="Test Caption",
            language="ja",
        )

        youtube_client.upload(
            path=video_path,
            title="Test Video",
            description="Test Description",
            tags=["test"],
            privacy_status="public",
            thumb=thumb_path,
            caption=caption,
            playlist_id="playlist123",
        )

        # 検証
        mock_upload_video.assert_called_once()
        mock_upload_thumbnail.assert_called_once_with("video123", thumb_path)
        mock_upload_subtitle.assert_called_once()
        mock_add_playlist.assert_called_once_with("video123", "playlist123")

    @patch.object(YouTubeClient, "upload_video")
    def test_upload_fails_when_video_upload_returns_none(
        self, mock_upload_video, youtube_client
    ):
        """動画アップロード失敗時にエラーを発生させる。"""
        # upload_video が None を返す
        mock_upload_video.return_value = None

        # テスト実行
        with pytest.raises(ResourceNotFoundError, match="アップロードに失敗"):
            youtube_client.upload(
                path=Path("/fake/path.mp4"),
                title="Test",
                description="Test",
            )
