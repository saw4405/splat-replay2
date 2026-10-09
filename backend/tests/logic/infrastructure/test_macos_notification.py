"""macOS 通知 adapter の callback と許可境界を確認する。"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import pytest

from splat_replay.domain.exceptions import (
    NotificationDeliveryError,
    NotificationPermissionDeniedError,
)
from splat_replay.infrastructure.adapters.system import macos_notification
from splat_replay.infrastructure.adapters.system.macos_notification import (
    MacOSNotificationAdapter,
)


class _FakeSettings:
    def __init__(self, status: int, alert_setting: int) -> None:
        self._status = status
        self._alert_setting = alert_setting

    def authorizationStatus(self) -> int:
        return self._status

    def alertSetting(self) -> int:
        return self._alert_setting


class _FakeContent:
    def __init__(self) -> None:
        self.title = ""
        self.body = ""
        self.sound: object | None = None

    def setTitle_(self, value: str) -> None:
        self.title = value

    def setBody_(self, value: str) -> None:
        self.body = value

    def setSound_(self, value: object) -> None:
        self.sound = value


class _FakeCenter:
    def __init__(
        self,
        *,
        granted: bool = True,
        add_error: object | None = None,
        withhold_callbacks: set[str] | None = None,
    ) -> None:
        self.granted = granted
        self.add_error = add_error
        self.withhold_callbacks = withhold_callbacks or set()
        self.authorization_status = 0
        self.options: int | None = None
        self.request: object | None = None

    def getNotificationSettingsWithCompletionHandler_(
        self, callback: Any
    ) -> None:
        if "settings" in self.withhold_callbacks:
            return
        alert_setting = 1 if self.authorization_status == 2 else 0
        callback(_FakeSettings(self.authorization_status, alert_setting))

    def requestAuthorizationWithOptions_completionHandler_(
        self, options: int, callback: Any
    ) -> None:
        self.options = options
        self.authorization_status = 2 if self.granted else 1
        if "authorization" in self.withhold_callbacks:
            return
        callback(self.granted, None)

    def addNotificationRequest_withCompletionHandler_(
        self, request: object, callback: Any
    ) -> None:
        self.request = request
        if "add" in self.withhold_callbacks:
            return
        callback(self.add_error)


def _adapter(
    monkeypatch: pytest.MonkeyPatch,
    center: _FakeCenter,
    *,
    bundle_id: str = "io.github.saw4405.splatreplay",
    display_name: str = "Splat Replay",
) -> MacOSNotificationAdapter:
    adapter = MacOSNotificationAdapter()
    bundle = SimpleNamespace(
        bundleIdentifier=lambda: bundle_id,
        infoDictionary=lambda: {"CFBundleDisplayName": display_name},
    )
    foundation = SimpleNamespace(
        NSBundle=SimpleNamespace(mainBundle=lambda: bundle)
    )
    user_notifications = SimpleNamespace(
        UNUserNotificationCenter=SimpleNamespace(
            currentNotificationCenter=lambda: center
        ),
        UNAuthorizationStatusNotDetermined=0,
        UNAuthorizationStatusAuthorized=2,
        UNAuthorizationStatusProvisional=3,
        UNAuthorizationOptionAlert=1,
        UNAuthorizationOptionSound=2,
        UNNotificationSettingEnabled=1,
        UNMutableNotificationContent=SimpleNamespace(
            alloc=lambda: SimpleNamespace(init=lambda: _FakeContent())
        ),
        UNNotificationSound=SimpleNamespace(defaultSound=lambda: "default"),
        UNNotificationRequest=SimpleNamespace(
            requestWithIdentifier_content_trigger_=(
                lambda identifier, content, trigger: (
                    identifier,
                    content,
                    trigger,
                )
            )
        ),
    )
    monkeypatch.setattr(
        adapter,
        "_load_frameworks",
        lambda: (foundation, user_notifications),
    )
    return adapter


@pytest.mark.asyncio
async def test_requests_permission_then_waits_for_notification_acceptance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    center = _FakeCenter()
    adapter = _adapter(monkeypatch, center)

    await adapter.send("録画開始", "録画を開始しました")

    assert center.options == 3
    assert isinstance(center.request, tuple)
    _, content, trigger = center.request
    assert isinstance(content, _FakeContent)
    assert content.title == "録画開始"
    assert content.body == "録画を開始しました"
    assert trigger is None


@pytest.mark.asyncio
async def test_denial_does_not_schedule_notification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    center = _FakeCenter(granted=False)
    adapter = _adapter(monkeypatch, center)

    with pytest.raises(NotificationPermissionDeniedError):
        await adapter.send("録画開始", "録画を開始しました")

    assert center.request is None


@pytest.mark.asyncio
async def test_notification_service_error_is_reported(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    center = _FakeCenter(add_error=RuntimeError("notification service failed"))
    center.authorization_status = 2
    adapter = _adapter(monkeypatch, center)

    with pytest.raises(
        NotificationDeliveryError, match="通知を登録できませんでした"
    ):
        await adapter.send("録画終了", "録画を終了しました")


@pytest.mark.asyncio
async def test_wrong_bundle_identity_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    center = _FakeCenter()
    adapter = _adapter(monkeypatch, center, display_name="Python")

    with pytest.raises(NotificationDeliveryError, match="bundle identity"):
        await adapter.send("録画開始", "録画を開始しました")

    assert center.options is None


@pytest.mark.parametrize(
    ("callback_stage", "error_detail"),
    [
        ("settings", "通知設定取得"),
        ("authorization", "通知許可要求"),
        ("add", "通知登録"),
    ],
)
@pytest.mark.asyncio
async def test_missing_callback_fails_with_bounded_stage_error(
    monkeypatch: pytest.MonkeyPatch,
    callback_stage: str,
    error_detail: str,
) -> None:
    monkeypatch.setattr(
        macos_notification, "_SETTINGS_CALLBACK_TIMEOUT_SECONDS", 0.01
    )
    monkeypatch.setattr(
        macos_notification, "_AUTHORIZATION_CALLBACK_TIMEOUT_SECONDS", 0.01
    )
    monkeypatch.setattr(
        macos_notification, "_ADD_CALLBACK_TIMEOUT_SECONDS", 0.01
    )
    center = _FakeCenter(withhold_callbacks={callback_stage})
    if callback_stage == "add":
        center.authorization_status = 2
    adapter = _adapter(monkeypatch, center)

    with pytest.raises(NotificationDeliveryError, match=error_detail):
        await asyncio.wait_for(
            adapter.send("録画開始", "録画を開始しました"), timeout=0.1
        )
