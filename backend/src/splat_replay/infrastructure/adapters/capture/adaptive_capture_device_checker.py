from __future__ import annotations

from collections.abc import Callable

from structlog.stdlib import BoundLogger

from splat_replay.application.interfaces import (
    CaptureDevicePort,
    CaptureDeviceSettingsView,
)
from splat_replay.infrastructure.test_input import (
    resolve_configured_test_video,
)


LiveCaptureDeviceCheckerFactory = Callable[
    [CaptureDeviceSettingsView, BoundLogger], CaptureDevicePort
]


def _build_live_checker(
    settings: CaptureDeviceSettingsView,
    logger: BoundLogger,
) -> CaptureDevicePort:
    """実機キャプチャデバイスのチェッカーを必要時に生成する。"""
    from splat_replay.infrastructure.adapters.capture.capture_device_checker import (
        CaptureDeviceChecker,
    )

    return CaptureDeviceChecker(settings, logger)


class AdaptiveCaptureDeviceChecker(CaptureDevicePort):
    """設定に応じて実機確認と動画ファイル確認を切り替える。"""

    def __init__(
        self,
        settings: CaptureDeviceSettingsView,
        logger: BoundLogger,
        *,
        live_checker_factory: LiveCaptureDeviceCheckerFactory
        | None = _build_live_checker,
    ) -> None:
        self._logger = logger
        self._settings = settings
        self._live_checker_factory = live_checker_factory
        self._live_checker: CaptureDevicePort | None = None

    def _resolve_live_checker(self) -> CaptureDevicePort:
        if self._live_checker is not None:
            return self._live_checker
        if self._live_checker_factory is None:
            raise RuntimeError(
                "リプレイ実行では実機キャプチャ確認へフォールバックできません"
            )
        self._live_checker = self._live_checker_factory(
            self._settings, self._logger
        )
        return self._live_checker

    def update_settings(self, settings: CaptureDeviceSettingsView) -> None:
        self._settings = settings
        if self._live_checker is not None:
            self._live_checker.update_settings(settings)

    def is_connected(self) -> bool:
        try:
            resolved = resolve_configured_test_video()
        except FileNotFoundError as exc:
            if self._live_checker_factory is None:
                raise RuntimeError(
                    "リプレイ入力が見つからないため実機確認へフォールバックできません"
                ) from exc
            return False

        if resolved is not None:
            connected = resolved.selected_path.exists()
            self._logger.debug(
                "動画ファイル入力の接続状態を確認しました",
                connected=connected,
                video_path=str(resolved.selected_path),
            )
            return connected

        return self._resolve_live_checker().is_connected()
