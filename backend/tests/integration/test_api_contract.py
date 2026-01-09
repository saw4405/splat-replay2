"""Frontend API Contract Tests.

このテストは、Frontend が依存する全エンドポイントの存在を保証する。
エンドポイントが誤って削除された場合、CI で即座に検出される。
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

# Frontend が依存する全エンドポイントの契約
# フォーマット: (メソッド, パス, 期待ステータスコード or リスト)
# ステータスコードが None の場合は 404 以外であることのみチェック
FRONTEND_API_CONTRACT: list[tuple[str, str, int | list[int] | None]] = [
    # ========================================
    # Setup Wizard Endpoints
    # ========================================
    ("GET", "/setup/status", 200),
    ("POST", "/setup/navigation/next", None),
    ("POST", "/setup/navigation/previous", None),
    ("POST", "/setup/start", None),
    ("POST", "/setup/complete", None),
    # System checks
    ("GET", "/setup/system/check/obs", 200),
    ("GET", "/setup/system/check/ffmpeg", 200),
    ("GET", "/setup/system/check/tesseract", 200),
    ("GET", "/setup/system/check/ndi", 200),
    ("GET", "/setup/system/check/font", 200),
    ("GET", "/setup/system/check/youtube", 200),
    # System setup
    ("POST", "/setup/system/setup/obs", None),
    ("POST", "/setup/system/setup/ffmpeg", None),
    ("POST", "/setup/system/setup/tesseract", None),
    # Configuration
    ("GET", "/setup/config/obs", 200),
    ("POST", "/setup/config/obs", None),
    ("GET", "/setup/devices/video", 200),
    ("POST", "/setup/config/capture-device", None),
    # ========================================
    # Main App Endpoints
    # ========================================
    # Health check
    ("GET", "/api/health", 200),
    # Settings
    ("GET", "/api/settings", 200),
    ("PUT", "/api/settings", None),
    # Device status
    ("GET", "/api/device/status", 200),
    # Recording control - /api/recorder/*
    ("POST", "/api/recorder/prepare", None),
    ("POST", "/api/recorder/start", None),
    ("POST", "/api/recorder/pause", None),
    ("POST", "/api/recorder/resume", None),
    ("POST", "/api/recorder/stop", None),
    ("GET", "/api/recorder/state", 200),
    # Recording metadata
    ("GET", "/api/recorder/metadata", 200),
    ("POST", "/api/recorder/metadata", None),
    # Preview
    ("GET", "/api/preview/latest", 200),
    # Assets - recorded videos
    ("GET", "/api/assets/recorded", 200),
    ("DELETE", "/api/assets/recorded/test-id", None),  # 存在確認のみ
    ("PUT", "/api/assets/recorded/test-id/metadata", None),
    # Assets - edited videos
    ("GET", "/api/assets/edited", 200),
    ("DELETE", "/api/assets/edited/test-id", None),
    # Subtitles
    ("GET", "/api/subtitles/recorded/test-id", None),
    ("PUT", "/api/subtitles/recorded/test-id", None),
    # Edit/Upload process
    ("POST", "/api/process/edit-upload", None),
    ("GET", "/api/process/status", 200),
    # Permission dialogs
    ("GET", "/api/settings/youtube-permission-dialog", None),
    ("PUT", "/api/settings/youtube-permission-dialog", None),
    ("GET", "/api/settings/camera-permission-dialog", None),
    ("PUT", "/api/settings/camera-permission-dialog", None),
]


@pytest.mark.parametrize("method,path,expected_status", FRONTEND_API_CONTRACT)
def test_frontend_api_contract(
    client: TestClient,
    method: str,
    path: str,
    expected_status: int | list[int] | None,
) -> None:
    """Frontend が依存する全エンドポイントが存在することを保証する。

    Args:
        client: FastAPI TestClient
        method: HTTPメソッド
        path: エンドポイントパス
        expected_status: 期待するステータスコード（None の場合は 404 以外を確認）
    """
    # エンドポイントにリクエストを送信
    response = client.request(method, path)

    # 404 Not Found でないことを確認（エンドポイントが実装されている）
    assert response.status_code != 404, (
        f"{method} {path} returned 404 Not Found - "
        f"endpoint does not exist or route is not registered"
    )

    # 期待するステータスコードのチェック
    if expected_status is not None:
        if isinstance(expected_status, list):
            assert response.status_code in expected_status, (
                f"{method} {path} returned {response.status_code}, "
                f"expected one of {expected_status}"
            )
        else:
            assert response.status_code == expected_status, (
                f"{method} {path} returned {response.status_code}, "
                f"expected {expected_status}"
            )


def test_no_duplicate_routes(client: TestClient) -> None:
    """ルートに重複がないことを確認する。"""
    routes = []
    for route in client.app.routes:  # type: ignore[attr-defined]
        if hasattr(route, "path") and hasattr(route, "methods"):
            for method in route.methods:  # type: ignore[attr-defined]
                route_key = (method, route.path)  # type: ignore[attr-defined]
                assert route_key not in routes, (
                    f"Duplicate route: {method} {route.path}"
                )  # type: ignore[attr-defined]
                routes.append(route_key)


def test_openapi_schema_generation(client: TestClient) -> None:
    """OpenAPI スキーマが正常に生成されることを確認する。"""
    schema = client.app.openapi()  # type: ignore[attr-defined]
    assert schema is not None
    assert "openapi" in schema
    assert "info" in schema
    assert "paths" in schema

    # 主要なエンドポイントがスキーマに含まれることを確認
    paths = schema["paths"]
    assert "/api/health" in paths
    assert "/api/settings" in paths
    assert "/api/recorder/start" in paths
