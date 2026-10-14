"""デスクトップ通知 API の成功・拒否・送信失敗契約。"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from splat_replay.application.interfaces import DesktopNotificationPort
from splat_replay.domain.exceptions import (
    NotificationDeliveryError,
    NotificationPermissionDeniedError,
)
import splat_replay.interface.web.routers.notifications as notifications

pytestmark = pytest.mark.contract


class _FakeNotificationSender:
    def __init__(self, failure: Exception | None = None) -> None:
        self.failure = failure
        self.calls: list[tuple[str, str]] = []

    async def send(self, title: str, body: str) -> None:
        self.calls.append((title, body))
        if self.failure is not None:
            raise self.failure


def _client(
    assets_dir: Path,
    sender: DesktopNotificationPort | None = None,
) -> TestClient:
    app = FastAPI()
    app.include_router(
        notifications.create_notifications_router(assets_dir, sender)
    )
    return TestClient(app)


def test_macos_success_waits_for_sender(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sender = _FakeNotificationSender()
    monkeypatch.setattr(notifications.sys, "platform", "darwin")

    with _client(Path("/missing"), sender) as client:
        response = client.post(
            "/api/notifications/send",
            json={"title": "録画開始", "body": "録画を開始しました"},
        )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["status"] == "success"
    assert sender.calls == [("録画開始", "録画を開始しました")]


@pytest.mark.parametrize(
    ("error", "expected_status"),
    [
        (
            NotificationPermissionDeniedError(
                "通知が拒否されました",
                error_code="NOTIFICATION_PERMISSION_DENIED",
            ),
            status.HTTP_403_FORBIDDEN,
        ),
        (
            NotificationDeliveryError(
                "通知登録に失敗しました",
                error_code="NOTIFICATION_DELIVERY_FAILED",
            ),
            status.HTTP_503_SERVICE_UNAVAILABLE,
        ),
    ],
)
def test_macos_failure_never_reports_success(
    monkeypatch: pytest.MonkeyPatch,
    error: Exception,
    expected_status: int,
) -> None:
    sender = _FakeNotificationSender(failure=error)
    monkeypatch.setattr(notifications.sys, "platform", "darwin")

    with _client(Path("/missing"), sender) as client:
        response = client.post(
            "/api/notifications/send",
            json={"title": "録画終了", "body": "録画を終了しました"},
        )

    assert response.status_code == expected_status
    assert response.json()["detail"]
    assert sender.calls == [("録画終了", "録画を終了しました")]


def test_windows_notification_behavior_is_preserved(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, object] = {}

    class FakeNotification:
        def __init__(self, **kwargs: object) -> None:
            calls["kwargs"] = kwargs

        def set_audio(self, audio: object, *, loop: bool) -> None:
            calls["audio"] = (audio, loop)

        def show(self) -> None:
            calls["shown"] = True

    monkeypatch.setattr(notifications.sys, "platform", "win32")
    monkeypatch.setattr(
        notifications, "Notification", FakeNotification, raising=False
    )
    monkeypatch.setattr(
        notifications,
        "audio",
        type("FakeAudio", (), {"Default": "default"}),
        raising=False,
    )

    with _client(Path("/missing")) as client:
        response = client.post(
            "/api/notifications/send",
            json={"title": "録画開始", "body": "録画を開始しました"},
        )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["status"] == "success"
    assert calls["kwargs"]["app_id"] == "Splat Replay"  # type: ignore[index]
    assert calls["audio"] == ("default", False)
    assert calls["shown"] is True
