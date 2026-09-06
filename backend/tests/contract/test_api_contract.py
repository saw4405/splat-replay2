"""Frontend API contract smoke tests.

このテストは、Frontend が依存する全エンドポイントの存在を保証する
route smoke です。
エンドポイントが誤って削除された場合、CI で即座に検出される。
schema / status / body の詳細契約は、専用の contract テストで固定する。
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.contract

# Frontend が依存する全エンドポイントの route smoke
# フォーマット: (メソッド, パス, 期待ステータスコード or リスト)
# ステータスコードが None の場合は route 存在確認として 404 以外のみチェック
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
    ("GET", "/api/settings/webview-render-mode", 200),
    ("PUT", "/api/settings", None),
    # Remote access
    ("GET", "/api/remote-access/status", 200),
    # Device status
    ("GET", "/api/device/status", 200),
    # Recording control - /api/recorder/*
    ("POST", "/api/recorder/prepare", None),
    ("POST", "/api/recorder/start", None),
    ("POST", "/api/recorder/pause", None),
    ("POST", "/api/recorder/resume", None),
    ("POST", "/api/recorder/stop", None),
    ("GET", "/api/recorder/state", 200),
    ("GET", "/api/recorder/auto-state", 200),
    ("GET", "/api/recorder/preview-mode", 200),
    ("GET", "/api/recorder/preview-frame", [200, 204]),
    # Recording metadata
    ("GET", "/api/recorder/metadata", 200),
    ("PATCH", "/api/recorder/metadata", None),
    ("GET", "/api/metadata/options", 200),
    # Assets - recorded videos
    ("GET", "/api/assets/recorded", 200),
    (
        "DELETE",
        "/api/assets/recorded/test-id",
        [200, 204, 404],
    ),  # 存在確認のみ（404等も許容）
    ("PATCH", "/api/assets/recorded/test-id/metadata", None),
    # Assets - edited videos
    ("GET", "/api/assets/edited", 200),
    ("DELETE", "/api/assets/edited/test-id", [200, 204, 404]),
    # Subtitles
    ("GET", "/api/subtitles/recorded/test-id", None),
    ("PUT", "/api/subtitles/recorded/test-id", None),
    # Edit/Upload process
    ("POST", "/api/process/edit-upload", None),
    ("GET", "/api/process/status", 200),
    ("DELETE", "/api/process/sleep", 200),
    # Permission dialogs
    ("GET", "/api/settings/youtube-permission-dialog", None),
    ("PUT", "/api/settings/youtube-permission-dialog", None),
    ("GET", "/api/settings/camera-permission-dialog", None),
    ("PUT", "/api/settings/camera-permission-dialog", None),
]


@pytest.mark.parametrize("method,path,expected_status", FRONTEND_API_CONTRACT)
def test_frontend_api_contract_smoke(
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

    # 404 Not Found でないことを確認（ただし期待ステータスに 404 が含まれる場合、または DELETE メソッドの場合は許容する）
    is_404_allowed = False
    if expected_status is not None:
        if isinstance(expected_status, list) and 404 in expected_status:
            is_404_allowed = True
        elif expected_status == 404:
            is_404_allowed = True
    if method == "DELETE":
        is_404_allowed = True

    if not is_404_allowed:
        assert response.status_code != 404, (
            f"{method} {path} returned 404 Not Found - "
            f"endpoint does not exist or route is not registered"
        )
        assert response.status_code != 500, (
            f"{method} {path} returned 500 Internal Server Error"
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
    assert "/api/settings/webview-render-mode" in paths
    assert "/api/remote-access/status" in paths
    assert "/api/recorder/start" in paths


def test_prepare_recording_response_does_not_include_audio_warning(
    client: TestClient,
) -> None:
    """POST /api/recorder/prepare - 音声検査を行わず警告を返さない。"""
    response = client.post("/api/recorder/prepare")

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "error": None,
        "state": None,
        "audio_health_warning": None,
    }


def test_auto_recorder_state_response_contract(client: TestClient) -> None:
    """GET /api/recorder/auto-state の状態値契約を保証する。"""
    response = client.get("/api/recorder/auto-state")

    assert response.status_code == 200
    assert response.json() == {
        "state": "idle",
        "power_state": "unknown",
    }
