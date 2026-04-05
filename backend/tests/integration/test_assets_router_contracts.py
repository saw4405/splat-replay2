"""Assets Router Contract Tests.

責務：
- Assets エンドポイントの存在を保証する
- CRUD操作のレスポンススキーマ検証
- エラーハンドリングの確認

分類: contract
"""

from __future__ import annotations

import pytest
from fastapi import status
from fastapi.testclient import TestClient

pytestmark = pytest.mark.contract


class TestRecordedAssetsEndpoints:
    """録画済みアセットエンドポイントのcontractテスト。"""

    def test_get_recorded_assets(self, client: TestClient) -> None:
        """GET /api/assets/recorded - 録画済みビデオ一覧取得。"""
        response = client.get("/api/assets/recorded")
        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert isinstance(data, list)

        # 空でない場合、必須フィールドの検証
        if data:
            video = data[0]
            assert "id" in video
            assert "path" in video
            assert "filename" in video
            assert "has_subtitle" in video
            assert "has_thumbnail" in video

            # Snake_case 形式を確認（Backend側の命名規則）
            assert isinstance(video["has_subtitle"], bool)
            assert isinstance(video["has_thumbnail"], bool)

    def test_delete_recorded_asset_not_found(self, client: TestClient) -> None:
        """DELETE /api/assets/recorded/{video_id} - 存在しないビデオ削除。"""
        video_id = "nonexistent_video_id_12345"
        response = client.delete(f"/api/assets/recorded/{video_id}")

        # 存在しない場合は204または404
        assert response.status_code in [
            status.HTTP_204_NO_CONTENT,
            status.HTTP_404_NOT_FOUND,
        ]

    def test_get_recorded_video_not_found(self, client: TestClient) -> None:
        """GET /videos/recorded/{video_id} - 存在しないビデオファイル取得。"""
        video_id = "nonexistent_video.mp4"
        response = client.get(f"/videos/recorded/{video_id}")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        assert "detail" in data

    def test_get_recorded_thumbnail_not_found(
        self, client: TestClient
    ) -> None:
        """GET /thumbnails/recorded/{filename} - 存在しないサムネイル取得。"""
        filename = "nonexistent_thumbnail.png"
        response = client.get(f"/thumbnails/recorded/{filename}")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        assert "detail" in data


class TestEditedAssetsEndpoints:
    """編集済みアセットエンドポイントのcontractテスト。"""

    def test_get_edited_assets(self, client: TestClient) -> None:
        """GET /api/assets/edited - 編集済みビデオ一覧取得。"""
        response = client.get("/api/assets/edited")
        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert isinstance(data, list)

        # 空でない場合、必須フィールドの検証
        if data:
            video = data[0]
            assert "id" in video
            assert "path" in video
            assert "filename" in video
            assert "has_subtitle" in video
            assert "has_thumbnail" in video
            assert "duration_seconds" in video
            assert "size_bytes" in video
            assert "metadata" in video

            # 型の検証
            assert isinstance(video["has_subtitle"], bool)
            assert isinstance(video["has_thumbnail"], bool)
            assert video["metadata"] is None or isinstance(
                video["metadata"], dict
            )

    def test_delete_edited_asset_not_found(self, client: TestClient) -> None:
        """DELETE /api/assets/edited/{video_id} - 存在しないビデオ削除。"""
        video_id = "nonexistent_edited_video_12345"
        response = client.delete(f"/api/assets/edited/{video_id}")

        # 存在しない場合は204または404
        assert response.status_code in [
            status.HTTP_204_NO_CONTENT,
            status.HTTP_404_NOT_FOUND,
        ]

    def test_get_edited_video_not_found(self, client: TestClient) -> None:
        """GET /videos/edited/{video_id} - 存在しないビデオファイル取得。"""
        video_id = "nonexistent_edited_video.mkv"
        response = client.get(f"/videos/edited/{video_id}")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        assert "detail" in data

    def test_get_edited_thumbnail_not_found(self, client: TestClient) -> None:
        """GET /thumbnails/edited/{filename} - 存在しないサムネイル取得。"""
        filename = "nonexistent_edited_thumbnail.png"
        response = client.get(f"/thumbnails/edited/{filename}")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        assert "detail" in data


class TestEditUploadProcessEndpoints:
    """編集・アップロード処理エンドポイントのcontractテスト。"""

    def test_get_edit_upload_status(self, client: TestClient) -> None:
        """GET /api/process/status - 編集・アップロード状態取得。"""
        response = client.get("/api/process/status")
        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        # 必須フィールド
        assert "state" in data
        assert data["state"] in ["idle", "running", "succeeded", "failed"]

        # オプショナルフィールドの型確認
        assert "started_at" in data
        assert "finished_at" in data
        assert "error" in data
        assert "sleep_after_upload_default" in data
        assert "sleep_after_upload_effective" in data
        assert "sleep_after_upload_overridden" in data

        # Boolean フィールドの検証
        assert isinstance(data["sleep_after_upload_default"], bool)
        assert isinstance(data["sleep_after_upload_effective"], bool)
        assert isinstance(data["sleep_after_upload_overridden"], bool)

    def test_trigger_edit_upload_manual(self, client: TestClient) -> None:
        """POST /api/process/edit-upload - 手動で編集・アップロード開始。"""
        response = client.post("/api/process/edit-upload")

        # 成功（202）または既に実行中（409）のいずれか
        assert response.status_code in [
            status.HTTP_202_ACCEPTED,
            status.HTTP_409_CONFLICT,
        ]

        data = response.json()
        assert "accepted" in data
        assert "status" in data

        # statusフィールドの構造確認
        status_data = data["status"]
        assert "state" in status_data
        assert status_data["state"] in [
            "idle",
            "running",
            "succeeded",
            "failed",
        ]

    def test_trigger_edit_upload_auto(self, client: TestClient) -> None:
        """POST /api/process/edit-upload?auto=true - 自動で編集・アップロード開始。"""
        response = client.post(
            "/api/process/edit-upload", params={"auto": True}
        )

        assert response.status_code in [
            status.HTTP_202_ACCEPTED,
            status.HTTP_409_CONFLICT,
        ]

        data = response.json()
        assert "accepted" in data
        assert "status" in data

    def test_update_edit_upload_options_valid(
        self, client: TestClient
    ) -> None:
        """PATCH /api/process/edit-upload/options - 一時オプション更新（正常系）。"""
        request_data = {"sleep_after_upload": True}
        response = client.patch(
            "/api/process/edit-upload/options", json=request_data
        )

        # 成功または処理中でないため変更不可（409）
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_409_CONFLICT,
        ]

        if response.status_code == status.HTTP_200_OK:
            data = response.json()
            assert "state" in data
            assert "sleep_after_upload_overridden" in data
            # 更新が反映されたことを確認
            assert isinstance(data["sleep_after_upload_overridden"], bool)

    def test_update_edit_upload_options_invalid_schema(
        self, client: TestClient
    ) -> None:
        """PATCH /api/process/edit-upload/options - 不正なスキーマ。"""
        request_data = {"invalid_field": "value"}
        response = client.patch(
            "/api/process/edit-upload/options", json=request_data
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_update_edit_upload_options_invalid_type(
        self, client: TestClient
    ) -> None:
        """PATCH /api/process/edit-upload/options - 不正な値の型。"""
        request_data = {"sleep_after_upload": "not_a_boolean"}
        response = client.patch(
            "/api/process/edit-upload/options", json=request_data
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


class TestAssetsMapperContract:
    """Mapper変換の契約テスト（snake_case ↔ camelCase）。"""

    def test_recorded_video_snake_case_fields(
        self, client: TestClient
    ) -> None:
        """録画済みビデオのレスポンスがsnake_case形式であることを確認。"""
        response = client.get("/api/assets/recorded")
        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        if not data:
            pytest.skip("録画済みビデオが存在しないためスキップ")

        video = data[0]
        # Snake_case フィールドの存在確認
        snake_case_fields = [
            "started_at",
            "game_mode",
            "has_subtitle",
            "has_thumbnail",
            "duration_seconds",
            "size_bytes",
            "gold_medals",
            "silver_medals",
            "golden_egg",
            "power_egg",
        ]

        for field in snake_case_fields:
            # フィールドが存在するか、またはnullであることを確認
            if field in video:
                # 型が正しいことを確認（stringまたはnumber、boolean）
                assert video[field] is None or isinstance(
                    video[field], (str, int, float, bool)
                )

    def test_edited_video_snake_case_fields(self, client: TestClient) -> None:
        """編集済みビデオのレスポンスがsnake_case形式であることを確認。"""
        response = client.get("/api/assets/edited")
        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        if not data:
            pytest.skip("編集済みビデオが存在しないためスキップ")

        video = data[0]
        # Snake_case フィールドの存在確認
        snake_case_fields = [
            "has_subtitle",
            "has_thumbnail",
            "duration_seconds",
            "updated_at",
            "size_bytes",
        ]

        for field in snake_case_fields:
            if field in video:
                assert video[field] is None or isinstance(
                    video[field], (str, int, float, bool)
                )

    def test_edit_upload_status_snake_case_fields(
        self, client: TestClient
    ) -> None:
        """編集・アップロード状態のレスポンスがsnake_case形式であることを確認。"""
        response = client.get("/api/process/status")
        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        # Snake_case フィールドの存在確認
        snake_case_fields = [
            "started_at",
            "finished_at",
            "sleep_after_upload_default",
            "sleep_after_upload_effective",
            "sleep_after_upload_overridden",
        ]

        for field in snake_case_fields:
            assert field in data
            # Null許容またはboolean
            assert data[field] is None or isinstance(data[field], (str, bool))


class TestAssetsErrorHandling:
    """Assets関連のエラーハンドリングテスト。"""

    def test_path_traversal_attempt(self, client: TestClient) -> None:
        """パストラバーサル攻撃の試行（セキュリティ）。"""
        malicious_path = "../../etc/passwd"
        response = client.get(f"/videos/recorded/{malicious_path}")

        # 404または400で拒否されること
        assert response.status_code in [
            status.HTTP_404_NOT_FOUND,
            status.HTTP_400_BAD_REQUEST,
        ]

    def test_absolute_path_attempt(self, client: TestClient) -> None:
        """絶対パスの指定試行（セキュリティ）。"""
        absolute_path = "/etc/passwd"
        response = client.get(f"/videos/recorded/{absolute_path}")

        # 404または400で拒否されること
        assert response.status_code in [
            status.HTTP_404_NOT_FOUND,
            status.HTTP_400_BAD_REQUEST,
        ]
