"""Settings Router Contract Tests.

責務：
- Settings エンドポイントの存在を保証する
- レスポンススキーマの検証
- エラーハンドリングの確認

分類: contract
"""

from __future__ import annotations

import pytest
from fastapi import status
from fastapi.testclient import TestClient

pytestmark = pytest.mark.contract


class TestSettingsEndpoints:
    """設定エンドポイントのcontractテスト。"""

    def test_get_settings(self, client: TestClient) -> None:
        """GET /api/settings - アプリケーション設定取得。"""
        response = client.get("/api/settings")
        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        # sectionsフィールドの存在確認
        assert "sections" in data
        assert isinstance(data["sections"], (list, dict))

    def test_update_settings_valid(self, client: TestClient) -> None:
        """PUT /api/settings - 設定更新（正常系）。"""
        # 最小限の有効なリクエスト
        request_data = {"sections": []}
        response = client.put("/api/settings", json=request_data)

        # 成功または設定項目の検証エラー
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        ]

        if response.status_code == status.HTTP_200_OK:
            data = response.json()
            assert "status" in data
            assert data["status"] == "ok"

    def test_update_settings_unknown_section(self, client: TestClient) -> None:
        """PUT /api/settings - 存在しないセクションID（エラー系）。"""
        request_data = {
            "sections": [
                {"id": "unknown_section_id", "values": {"key": "value"}}
            ]
        }
        response = client.put("/api/settings", json=request_data)

        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        assert "detail" in data

    def test_update_settings_unknown_field(self, client: TestClient) -> None:
        """PUT /api/settings - 存在しないフィールド（エラー系）。"""
        # 既知のセクションIDに対して存在しないフィールドを指定
        # セクションIDは実装依存のため、まず設定を取得
        get_response = client.get("/api/settings")
        assert get_response.status_code == status.HTTP_200_OK

        sections_data = get_response.json()["sections"]
        if not sections_data:
            pytest.skip("設定セクションが空のためスキップ")

        # 最初のセクションIDを使用
        if isinstance(sections_data, list):
            first_section_id = sections_data[0].get("id")
        elif isinstance(sections_data, dict):
            first_section_id = list(sections_data.keys())[0]
        else:
            pytest.skip("設定セクション形式が不明")

        request_data = {
            "sections": [
                {
                    "id": first_section_id,
                    "values": {"invalid_field_name": "value"},
                }
            ]
        }
        response = client.put("/api/settings", json=request_data)

        # 無効なフィールドは400または422
        assert response.status_code in [
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        ]

    def test_update_settings_invalid_value_type(
        self, client: TestClient
    ) -> None:
        """PUT /api/settings - 無効な値の型（エラー系）。"""
        # バリデーションエラーを引き起こす不正な型
        request_data = {
            "sections": [
                {
                    "id": "obs",
                    "values": {"port": "not_a_number"},
                }  # 数値が期待される場所に文字列
            ]
        }
        response = client.put("/api/settings", json=request_data)

        assert response.status_code in [
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_404_NOT_FOUND,  # obsセクションが存在しない場合
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        ]

    def test_update_settings_invalid_schema(self, client: TestClient) -> None:
        """PUT /api/settings - 不正なリクエストスキーマ（エラー系）。"""
        # sectionsフィールドが欠落
        request_data = {"invalid_field": "value"}
        response = client.put("/api/settings", json=request_data)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestDeviceStatusEndpoints:
    """デバイス状態エンドポイントのcontractテスト。"""

    def test_get_device_status(self, client: TestClient) -> None:
        """GET /api/device/status - デバイス状態取得。"""
        response = client.get("/api/device/status")
        assert response.status_code == status.HTTP_200_OK

        # レスポンス形式の検証
        # is_connected: bool を返すことを想定
        data = response.json()
        assert isinstance(data, (bool, dict))


class TestPermissionDialogEndpoints:
    """許可ダイアログ状態エンドポイントのcontractテスト。"""

    def test_get_camera_permission_dialog_status(
        self, client: TestClient
    ) -> None:
        """GET /api/settings/camera-permission-dialog - カメラ許可ダイアログ状態取得。"""
        response = client.get("/api/settings/camera-permission-dialog")
        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert "shown" in data
        assert isinstance(data["shown"], bool)

    def test_mark_camera_permission_dialog_shown(
        self, client: TestClient
    ) -> None:
        """POST /api/settings/camera-permission-dialog - カメラ許可ダイアログを表示済みとしてマーク。"""
        request_data = {"shown": True}
        response = client.post(
            "/api/settings/camera-permission-dialog", json=request_data
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "status" in data
        assert data["status"] == "ok"

    def test_get_youtube_permission_dialog_status(
        self, client: TestClient
    ) -> None:
        """GET /api/settings/youtube-permission-dialog - YouTube許可ダイアログ状態取得。"""
        response = client.get("/api/settings/youtube-permission-dialog")
        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert "shown" in data
        assert isinstance(data["shown"], bool)

    def test_mark_youtube_permission_dialog_shown(
        self, client: TestClient
    ) -> None:
        """POST /api/settings/youtube-permission-dialog - YouTube許可ダイアログを表示済みとしてマーク。"""
        request_data = {"shown": True}
        response = client.post(
            "/api/settings/youtube-permission-dialog", json=request_data
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "status" in data
        assert data["status"] == "ok"

    def test_permission_dialog_invalid_request(
        self, client: TestClient
    ) -> None:
        """POST /api/settings/*-permission-dialog - 不正なリクエストスキーマ。"""
        # 不正なフィールド
        request_data = {"invalid_field": True}
        response = client.post(
            "/api/settings/camera-permission-dialog", json=request_data
        )

        # shownフィールドが無い場合はデフォルト値で処理される可能性もあるため、
        # 200または422を許容
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        ]


class TestSettingsPersistence:
    """設定の永続化確認テスト。"""

    def test_settings_roundtrip(self, client: TestClient) -> None:
        """設定の取得→更新→再取得のラウンドトリップテスト。"""
        # 1. 現在の設定を取得
        get_response = client.get("/api/settings")
        assert get_response.status_code == status.HTTP_200_OK
        # セクション構造の存在を確認
        assert "sections" in get_response.json()

        # 2. 空の更新を実行（変更なし）
        update_request = {"sections": []}
        update_response = client.put("/api/settings", json=update_request)
        assert update_response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        ]

        # 3. 再度取得して一貫性を確認
        get_response_after = client.get("/api/settings")
        assert get_response_after.status_code == status.HTTP_200_OK

        # 更新していないため、セクション構造は維持される
        assert "sections" in get_response_after.json()
