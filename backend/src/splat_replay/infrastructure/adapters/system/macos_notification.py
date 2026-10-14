"""macOS UserNotifications adapter."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from importlib import import_module
from typing import Any
from uuid import uuid4

import structlog

from splat_replay.application.interfaces import DesktopNotificationPort
from splat_replay.domain.exceptions import (
    NotificationDeliveryError,
    NotificationPermissionDeniedError,
)

_BUNDLE_IDENTIFIER = "io.github.saw4405.splatreplay"
_BUNDLE_DISPLAY_NAME = "Splat Replay"
_SETTINGS_CALLBACK_TIMEOUT_SECONDS = 10.0
_AUTHORIZATION_CALLBACK_TIMEOUT_SECONDS = 30.0
_ADD_CALLBACK_TIMEOUT_SECONDS = 10.0
_LOGGER = structlog.get_logger(__name__)


class MacOSNotificationAdapter(DesktopNotificationPort):
    """UserNotifications に許可を求め、通知要求の登録完了を待つ。"""

    async def send(self, title: str, body: str) -> None:
        try:
            await self._send(title, body)
        except (
            NotificationPermissionDeniedError,
            NotificationDeliveryError,
        ):
            raise
        except Exception as error:
            raise NotificationDeliveryError(
                "macOS の通知を登録できませんでした",
                error_code="NOTIFICATION_DELIVERY_FAILED",
                cause=error,
            ) from error

    async def _send(self, title: str, body: str) -> None:
        foundation, user_notifications = self._load_frameworks()
        bundle = foundation.NSBundle.mainBundle()
        info = bundle.infoDictionary() or {}
        if (
            bundle.bundleIdentifier() != _BUNDLE_IDENTIFIER
            or info.get("CFBundleDisplayName") != _BUNDLE_DISPLAY_NAME
        ):
            raise NotificationDeliveryError(
                "Splat Replay.app の bundle identity を確認できません",
                error_code="NOTIFICATION_DELIVERY_FAILED",
            )

        center_type = user_notifications.UNUserNotificationCenter
        center = center_type.currentNotificationCenter()
        settings = await self._get_settings(center)
        if (
            settings.authorizationStatus()
            == user_notifications.UNAuthorizationStatusNotDetermined
        ):
            authorize = (
                center.requestAuthorizationWithOptions_completionHandler_
            )
            granted, error = await self._callback(
                lambda callback: authorize(
                    user_notifications.UNAuthorizationOptionAlert
                    | user_notifications.UNAuthorizationOptionSound,
                    callback,
                ),
                operation="通知許可要求",
                timeout_seconds=_AUTHORIZATION_CALLBACK_TIMEOUT_SECONDS,
            )
            if error is not None:
                raise RuntimeError(f"通知許可を要求できませんでした: {error}")
            if not granted:
                raise NotificationPermissionDeniedError(
                    "macOS の通知が許可されませんでした",
                    error_code="NOTIFICATION_PERMISSION_DENIED",
                )
            settings = await self._get_settings(center)

        if (
            settings.authorizationStatus()
            not in {
                user_notifications.UNAuthorizationStatusAuthorized,
                user_notifications.UNAuthorizationStatusProvisional,
            }
            or settings.alertSetting()
            != user_notifications.UNNotificationSettingEnabled
        ):
            raise NotificationPermissionDeniedError(
                "macOS のシステム設定で Splat Replay の通知を許可してください",
                error_code="NOTIFICATION_PERMISSION_DENIED",
            )

        content = (
            user_notifications.UNMutableNotificationContent.alloc().init()
        )
        content.setTitle_(title)
        content.setBody_(body)
        content.setSound_(
            user_notifications.UNNotificationSound.defaultSound()
        )
        request_type = user_notifications.UNNotificationRequest
        request = request_type.requestWithIdentifier_content_trigger_(
            str(uuid4()), content, None
        )
        add_request = center.addNotificationRequest_withCompletionHandler_
        (error,) = await self._callback(
            lambda callback: add_request(request, callback),
            operation="通知登録",
            timeout_seconds=_ADD_CALLBACK_TIMEOUT_SECONDS,
        )
        if error is not None:
            raise RuntimeError(f"macOS が通知を受け付けませんでした: {error}")

    @staticmethod
    def _load_frameworks() -> tuple[Any, Any]:
        return import_module("Foundation"), import_module("UserNotifications")

    @staticmethod
    async def _get_settings(center: Any) -> Any:
        (settings,) = await MacOSNotificationAdapter._callback(
            center.getNotificationSettingsWithCompletionHandler_,
            operation="通知設定取得",
            timeout_seconds=_SETTINGS_CALLBACK_TIMEOUT_SECONDS,
        )
        if settings is None:
            raise RuntimeError("macOS の通知設定を取得できませんでした")
        return settings

    @staticmethod
    async def _callback(
        register: Callable[[Callable[..., None]], object],
        *,
        operation: str,
        timeout_seconds: float,
    ) -> tuple[object, ...]:
        loop = asyncio.get_running_loop()
        result: asyncio.Future[tuple[object, ...]] = loop.create_future()

        def completed(*values: object) -> None:
            def finish() -> None:
                if not result.done():
                    result.set_result(values)
                    _LOGGER.info(
                        "macOS notification callback completed",
                        operation=operation,
                    )

            loop.call_soon_threadsafe(finish)

        _LOGGER.info(
            "macOS notification callback waiting",
            operation=operation,
            timeout_seconds=timeout_seconds,
        )
        try:
            register(completed)
        except Exception as error:
            raise NotificationDeliveryError(
                f"macOS の{operation}を開始できませんでした",
                error_code="NOTIFICATION_CALLBACK_START_FAILED",
                cause=error,
            ) from error

        try:
            return await asyncio.wait_for(result, timeout=timeout_seconds)
        except TimeoutError as error:
            _LOGGER.warning(
                "macOS notification callback timed out",
                operation=operation,
                timeout_seconds=timeout_seconds,
            )
            raise NotificationDeliveryError(
                f"macOS の{operation} callback が"
                f" {timeout_seconds:g} 秒以内に返りませんでした",
                error_code="NOTIFICATION_CALLBACK_TIMEOUT",
                cause=error,
            ) from error
