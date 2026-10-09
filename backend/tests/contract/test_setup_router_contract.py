"""Setup Router Contract Tests.

責務：
- Setup エンドポイントの存在を保証する
- レスポンススキーマの検証
- エラーハンドリングの確認

分類: contract
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from splat_replay.application.services import RecordingPreparationService
from splat_replay.application.services.setup.system_check_service import (
    SoftwareCheckResult,
    SystemCheckService,
)
from splat_replay.application.services.setup.system_setup_service import (
    SystemSetupService,
)
import splat_replay.interface.web.schemas.setup as setup_schemas

pytestmark = pytest.mark.contract


class TestSetupStatusEndpoints:
    """セットアップ状態エンドポイントのcontractテスト。"""

    def test_get_installation_status(self, client: TestClient) -> None:
        """GET /setup/status - セットアップ状態取得。"""
        response = client.get("/setup/status")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # 必須フィールドの存在確認
        assert "is_completed" in data
        assert "current_step" in data
        assert "completed_steps" in data
        assert "skipped_steps" in data
        assert "progress_percentage" in data
        assert "remaining_steps" in data
        assert "step_details" in data

        # 型の検証
        assert isinstance(data["is_completed"], bool)
        assert isinstance(data["current_step"], str)
        assert isinstance(data["completed_steps"], list)
        assert isinstance(data["skipped_steps"], list)
        assert isinstance(data["progress_percentage"], (int, float))
        assert isinstance(data["remaining_steps"], list)
        assert isinstance(data["step_details"], dict)

    @pytest.mark.parametrize(
        ("system_name", "expected_platform"),
        [
            ("Windows", "windows"),
            ("Darwin", "macos"),
            ("Linux", "unknown"),
        ],
    )
    def test_server_platform_is_in_status_navigation_and_lifecycle_responses(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
        system_name: str,
        expected_platform: str,
    ) -> None:
        """全OS判定値をstatus・navigation・lifecycle応答へ含める。"""
        monkeypatch.setattr(
            setup_schemas.platform, "system", lambda: system_name
        )

        responses = [
            client.get("/setup/status"),
            client.post("/setup/start"),
            client.post("/setup/steps/hardware_check/skip"),
            client.post("/setup/navigation/next"),
            client.post("/setup/navigation/previous"),
            client.post("/setup/complete"),
        ]

        assert all(
            response.status_code == status.HTTP_200_OK
            for response in responses
        )
        assert [
            response.json()["server_platform"] for response in responses
        ] == [expected_platform] * len(responses)


class TestSetupNavigationEndpoints:
    """セットアップナビゲーションエンドポイントのcontractテスト。"""

    def test_navigate_next(self, client: TestClient) -> None:
        """POST /setup/navigation/next - 次のステップへ進む。"""
        response = client.post("/setup/navigation/next")

        # 成功または既に最終ステップ（400）のいずれか
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_400_BAD_REQUEST,
        ]

        if response.status_code == status.HTTP_200_OK:
            data = response.json()
            assert "is_completed" in data
            assert "current_step" in data

    def test_navigate_previous(self, client: TestClient) -> None:
        """POST /setup/navigation/previous - 前のステップへ戻る。"""
        response = client.post("/setup/navigation/previous")

        # 成功または既に最初のステップ（400）のいずれか
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_400_BAD_REQUEST,
        ]


class TestSetupLifecycleEndpoints:
    """セットアップライフサイクルエンドポイントのcontractテスト。"""

    def test_start_installation(self, client: TestClient) -> None:
        """POST /setup/start - セットアップ開始。"""
        response = client.post("/setup/start")

        # 既に開始済みの場合も含めて成功系を許容
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_400_BAD_REQUEST,
        ]

        if response.status_code == status.HTTP_200_OK:
            data = response.json()
            assert "is_completed" in data

    def test_complete_installation(self, client: TestClient) -> None:
        """POST /setup/complete - セットアップ完了。"""
        response = client.post("/setup/complete")

        # 未完了の可能性もあるため複数ステータスを許容
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_400_BAD_REQUEST,
        ]


class TestSetupStepManagementEndpoints:
    """セットアップステップ管理エンドポイントのcontractテスト。"""

    @pytest.mark.parametrize(
        "step_name",
        [
            "hardware_check",
            "obs_setup",
            "ffmpeg_setup",
            "tesseract_setup",
            "font_installation",
            "youtube_setup",
        ],
    )
    def test_complete_step_valid(
        self, client: TestClient, step_name: str
    ) -> None:
        """POST /setup/steps/{step_name}/complete - ステップ完了。"""
        response = client.post(f"/setup/steps/{step_name}/complete")

        # 成功または既に完了済み
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_400_BAD_REQUEST,
        ]

    def test_complete_step_invalid_name(self, client: TestClient) -> None:
        """POST /setup/steps/{step_name}/complete - 無効なステップ名。"""
        response = client.post("/setup/steps/invalid_step_name/complete")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert "detail" in data

    def test_skip_step(self, client: TestClient) -> None:
        """POST /setup/steps/{step_name}/skip - ステップスキップ。"""
        step_name = "font_installation"
        response = client.post(f"/setup/steps/{step_name}/skip")

        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_400_BAD_REQUEST,
        ]

    def test_update_substep_completion_valid(self, client: TestClient) -> None:
        """POST /setup/steps/{step_name}/substeps/{substep_id} - サブステップ完了更新。"""
        step_name = "hardware_check"
        substep_id = "video_device"
        response = client.post(
            f"/setup/steps/{step_name}/substeps/{substep_id}",
            params={"completed": True},
        )

        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_400_BAD_REQUEST,
        ]

    def test_update_substep_completion_invalid_step(
        self, client: TestClient
    ) -> None:
        """POST /setup/steps/{step_name}/substeps/{substep_id} - 無効なステップ名。"""
        step_name = "invalid_step"
        substep_id = "test_substep"
        response = client.post(
            f"/setup/steps/{step_name}/substeps/{substep_id}",
            params={"completed": True},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestSystemCheckEndpoints:
    """システムチェックエンドポイントのcontractテスト。"""

    @pytest.mark.parametrize(
        "software",
        ["obs", "ffmpeg", "tesseract", "flac", "ndi", "font", "youtube"],
    )
    def test_check_system_software(
        self,
        client: TestClient,
        software: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """GET /setup/system/check/{software} - システムソフトウェアチェック。"""
        for method_name in (
            "check_obs_installation",
            "check_ffmpeg_installation",
            "check_tesseract_installation",
            "check_flac_installation",
            "check_ndi_runtime_installation",
            "check_font_installation",
            "check_youtube_credentials",
        ):
            monkeypatch.setattr(
                SystemCheckService,
                method_name,
                lambda self: SoftwareCheckResult(is_installed=False),
            )

        response = client.get(f"/setup/system/check/{software}")
        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        # 必須フィールド
        assert "is_installed" in data
        assert isinstance(data["is_installed"], bool)

        # オプショナルフィールドの存在と型検証
        assert "version" in data
        assert data["version"] is None or isinstance(data["version"], str)

        assert "installation_path" in data
        assert data["installation_path"] is None or isinstance(
            data["installation_path"], str
        )

        assert "error_message" in data
        assert data["error_message"] is None or isinstance(
            data["error_message"], str
        )

    def test_check_system_software_invalid(self, client: TestClient) -> None:
        """GET /setup/system/check/{software} - 無効なソフトウェア名。"""
        response = client.get("/setup/system/check/invalid_software")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_font_check_returns_the_resolved_os_font_path(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """フォント確認は代替 OS フォントの利用可能性を返す。"""
        fallback_path = Path("/System/Library/Fonts/Hiragino Sans.ttc")
        monkeypatch.setattr(
            SystemCheckService,
            "check_font_installation",
            lambda self: SoftwareCheckResult(
                is_installed=True, installation_path=fallback_path
            ),
        )

        response = client.get("/setup/system/check/font")

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {
            "is_installed": True,
            "version": None,
            "installation_path": str(fallback_path),
            "error_message": None,
        }


class TestSystemSetupEndpoints:
    """システムセットアップエンドポイントのcontractテスト。"""

    @pytest.mark.parametrize(
        "endpoint",
        [
            "/setup/system/setup/ffmpeg",
            "/setup/system/setup/obs",
            "/setup/system/setup/tesseract",
            "/setup/system/setup/flac",
        ],
    )
    def test_system_setup_endpoints(
        self,
        client: TestClient,
        endpoint: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """POST /setup/system/setup/{software} - システムセットアップ実行。"""
        for method_name in (
            "setup_ffmpeg",
            "setup_obs",
            "setup_tesseract",
            "setup_flac",
        ):
            monkeypatch.setattr(
                SystemSetupService,
                method_name,
                lambda self: SoftwareCheckResult(is_installed=False),
            )

        response = client.post(endpoint)

        # セットアップ成功または既にインストール済み
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_500_INTERNAL_SERVER_ERROR,  # セットアップ失敗も想定
        ]

        if response.status_code == status.HTTP_200_OK:
            data = response.json()
            assert "is_installed" in data
            assert isinstance(data["is_installed"], bool)


class TestOBSConfigEndpoints:
    """OBS設定エンドポイントのcontractテスト。"""

    def test_get_obs_config(self, client: TestClient) -> None:
        """GET /setup/config/obs - OBS設定取得。"""
        response = client.get("/setup/config/obs")
        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert "websocket_password" in data
        assert "capture_device_name" in data

    def test_post_obs_websocket_password(self, client: TestClient) -> None:
        """POST /setup/config/obs/websocket-password - WebSocketパスワード設定（正常系）。"""
        request_data = {"password": "test_password_123"}
        response = client.post(
            "/setup/config/obs/websocket-password", json=request_data
        )

        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_400_BAD_REQUEST,
        ]

    def test_post_obs_websocket_password_invalid_schema(
        self, client: TestClient
    ) -> None:
        """POST /setup/config/obs/websocket-password - 不正なスキーマ。"""
        request_data = {"invalid_field": "value"}
        response = client.post(
            "/setup/config/obs/websocket-password", json=request_data
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


class TestDeviceEndpoints:
    """デバイス関連エンドポイントのcontractテスト。"""

    def test_get_video_devices(self, client: TestClient) -> None:
        """GET /setup/devices/video - ビデオデバイス一覧取得。"""
        response = client.get("/setup/devices/video")
        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert "devices" in data
        assert isinstance(data["devices"], list)

    def test_get_microphone_devices(self, client: TestClient) -> None:
        """GET /setup/devices/microphone - マイクデバイス一覧取得。"""
        response = client.get("/setup/devices/microphone")

        # 実装されている場合は200、未実装の場合は404
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
        ]

    def test_post_capture_device_valid(self, client: TestClient) -> None:
        """POST /setup/config/capture-device - キャプチャデバイス設定（正常系）。"""
        # 実装状況により成功/失敗が分かれる
        request_data = {"device_name": "Test Device"}
        response = client.post(
            "/setup/config/capture-device", json=request_data
        )

        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_422_UNPROCESSABLE_CONTENT,
        ]

    def test_post_capture_device_saves_name(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """POST /setup/config/capture-device saves the selected name."""
        saved_names: list[str] = []

        def _fake_save(
            self: RecordingPreparationService, device_name: str
        ) -> None:
            saved_names.append(device_name)

        monkeypatch.setattr(
            RecordingPreparationService, "save_capture_device", _fake_save
        )

        response = client.post(
            "/setup/config/capture-device",
            json={"device_name": "Test Device"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["message"] == "Capture device saved successfully"
        assert saved_names == ["Test Device"]


class TestYouTubeConfigEndpoints:
    """YouTube設定エンドポイントのcontractテスト。"""

    def test_post_youtube_privacy_status(self, client: TestClient) -> None:
        """POST /setup/config/youtube/privacy-status - YouTubeプライバシー設定。"""
        request_data = {"status": "private"}
        response = client.post(
            "/setup/config/youtube/privacy-status", json=request_data
        )

        # 実装により成功/失敗が分かれる
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_422_UNPROCESSABLE_CONTENT,
        ]
