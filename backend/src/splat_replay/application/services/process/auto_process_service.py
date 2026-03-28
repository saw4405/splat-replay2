"""Auto process service.

電源OFF検出時などをトリガーに、自動編集・アップロード・スリープの一連の処理を制御する。
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, Awaitable, Callable, cast

from splat_replay.application.interfaces import (
    ConfigPort,
    EventBusPort,
    LoggerPort,
    VideoAssetRepositoryPort,
)
from splat_replay.application.services.system.power_manager import PowerManager
from splat_replay.application.use_cases.assets.start_edit_upload import (
    StartEditUploadUseCase,
)
from splat_replay.domain.events import (
    AutoProcessPending,
    AutoProcessStarted,
    AutoSleepCancelled,
    AutoSleepPending,
    AutoSleepStarted,
    EditUploadCompleted,
    PowerOffDetected,
)

if TYPE_CHECKING:
    pass


class AutoProcessService:
    """自動処理サービス。

    責務:
    - 電源OFF検知時の自動編集・アップロード開始
    - 編集・アップロード完了後の自動スリープ
    """

    def __init__(
        self,
        event_bus: EventBusPort,
        start_edit_upload_uc: StartEditUploadUseCase,
        power_manager: PowerManager,
        config: ConfigPort,
        logger: LoggerPort,
        repo: VideoAssetRepositoryPort,
        sleep_func: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self.event_bus = event_bus
        self.start_edit_upload_uc = start_edit_upload_uc
        self.power_manager = power_manager
        self.config = config
        self.logger = logger
        self.repo = repo
        self._sleep = sleep_func
        self._is_auto_processing = False
        self._auto_sleep_allowed = False
        self._pending_sleep_after_upload: bool | None = None
        # ユーザーがトグルで明示的にスリープをキャンセルしたかどうか
        self._sleep_cancelled_by_user = False

        # イベント購読
        # Note: EventBusPortの実装によってはsubscribeメソッドのシグネチャが異なる可能性があるが、
        # ここでは一般的なPub/Subパターンとして実装。
        # 実際には、bootstrap/web_app.py などでイベントバスへの登録を行う必要があるかもしれない。
        # punqで解決されたインスタンスなら、ここでsubscribeを呼ぶ想定。

    async def start(self) -> None:
        """サービスのイベントループを開始する。"""
        # 必要なイベントのみ購読
        sub = self.event_bus.subscribe(
            event_types={
                PowerOffDetected.EVENT_TYPE,
                EditUploadCompleted.EVENT_TYPE,
                AutoSleepPending.EVENT_TYPE,
            }
        )
        self.logger.info("AutoProcessService started")

        try:
            while True:
                # ポーリング (非ブロッキングで少し待機)
                # Note: EventSubscription Protocol defines poll(max_items) -> list[Event]
                # Event is from infrastructure.messaging
                events = sub.poll(max_items=10)

                for event in events:
                    # event is infrastructure.messaging.Event
                    ev = cast(Any, event)
                    if ev.type == PowerOffDetected.EVENT_TYPE:
                        # payloadから再構築する必要はないが、型ヒントのために使い分けると良い
                        # ここでは直接処理へ
                        await self.handle_power_off_detected(ev)
                    elif ev.type == EditUploadCompleted.EVENT_TYPE:
                        await self.handle_edit_upload_completed(ev)
                    elif ev.type == AutoSleepPending.EVENT_TYPE:
                        self.handle_auto_sleep_pending(ev)

                await asyncio.sleep(1.0)
        except asyncio.CancelledError:
            self.logger.info("AutoProcessService stopped")
            sub.close()
            raise

    async def handle_power_off_detected(self, event: object) -> None:
        """電源OFF検出時の処理。"""
        ev = cast(Any, event)
        is_final = False
        if hasattr(ev, "payload") and isinstance(ev.payload, dict):
            is_final = bool(ev.payload.get("final", False))
        if not is_final:
            return

        settings = self.config.get_behavior_settings()
        if not settings.edit_after_power_off:
            return

        if self._is_auto_processing or self.start_edit_upload_uc.is_running():
            self.logger.info(
                "編集・アップロードが実行中のため自動処理通知をスキップします"
            )
            return

        if not self.repo.list_recordings():
            self.logger.info(
                "録画済み動画がないため自動処理通知をスキップします"
            )
            return

        self.logger.info(
            "電源OFFを検出しました。自動編集・アップロードをスケジュールします。"
        )

        # 1. 自動処理開始予告イベントを発行
        timeout_seconds = 15.0
        self.event_bus.publish_domain_event(
            AutoProcessPending(
                timeout_seconds=timeout_seconds,
                message=(
                    "電源OFFを検知しました。15秒後に自動編集・アップロードを開始します。"
                    "不要な場合はキャンセルしてください。"
                ),
            )
        )

    async def start_auto_process(self) -> None:
        """自動処理を開始する。"""
        if self._is_auto_processing:
            raise RuntimeError("自動処理が既に実行中です")

        self._auto_sleep_allowed = False
        self._sleep_cancelled_by_user = (
            False  # 新規プロセスではキャンセル状態をリセット
        )
        self._is_auto_processing = True

        try:
            await self.start_edit_upload_uc.execute(trigger="auto")
        except Exception as e:
            self.logger.error(
                "自動編集・アップロードの開始に失敗しました", error=str(e)
            )
            self._is_auto_processing = False
            raise

        self.logger.info("自動編集・アップロードを開始します。")
        self.event_bus.publish_domain_event(AutoProcessStarted())

    def on_new_execution(self) -> None:
        """新規プロセス開始時にユーザーキャンセルフラグをリセットする。"""
        self._sleep_cancelled_by_user = False

    async def handle_edit_upload_completed(self, event_obj: object) -> None:
        """編集・アップロード完了時の処理。"""
        # event_obj is infrastructure.messaging.Event
        # payload has 'success' key

        trigger = "manual"
        ev = cast(Any, event_obj)
        if hasattr(ev, "payload") and isinstance(ev.payload, dict):
            trigger = str(ev.payload.get("trigger", "manual"))

        # Payload access depends on Event structure.
        # infrastructure.messaging.Event has .payload dict
        success = False
        sleep_after_upload = False
        if hasattr(ev, "payload") and isinstance(ev.payload, dict):
            success = bool(ev.payload.get("success", False))
            sleep_after_upload_value = ev.payload.get("sleep_after_upload")
            if isinstance(sleep_after_upload_value, bool):
                sleep_after_upload = sleep_after_upload_value

        if self._is_auto_processing:
            self._is_auto_processing = False

        if trigger == "manual":
            if self._sleep_cancelled_by_user:
                # ユーザーがトグルでスリープをキャンセルしたため許可しない
                self._auto_sleep_allowed = False
                self._pending_sleep_after_upload = None
            else:
                self._auto_sleep_allowed = sleep_after_upload
                self._pending_sleep_after_upload = (
                    sleep_after_upload if sleep_after_upload else None
                )
            return

        if not success:
            self.logger.warning(
                "自動編集・アップロードが失敗しました。スリープ設定が有効なら通知します。"
            )

        if self._sleep_cancelled_by_user or not sleep_after_upload:
            self._auto_sleep_allowed = False
            self._pending_sleep_after_upload = None
            if not self._sleep_cancelled_by_user:
                self.logger.info(
                    "自動スリープしない設定のため、スリープ通知をスキップします。"
                )
            return

        self._auto_sleep_allowed = True
        self._pending_sleep_after_upload = sleep_after_upload
        self.event_bus.publish_domain_event(
            AutoSleepPending(
                timeout_seconds=15.0,
                message=(
                    "編集・アップロードが完了しました。15秒後に自動スリープします。"
                    "続けて作業する場合はキャンセルしてください。"
                ),
                sleep_after_upload=sleep_after_upload,
            )
        )

    def handle_auto_sleep_pending(self, event_obj: object) -> None:
        """自動スリープの開始待ちを受け取ったときの処理。"""
        if self._sleep_cancelled_by_user:
            # ユーザーがトグルでスリープをキャンセルしたため許可しない
            self._auto_sleep_allowed = False
            self._pending_sleep_after_upload = None
            return
        self._auto_sleep_allowed = True
        ev = cast(Any, event_obj)
        if hasattr(ev, "payload") and isinstance(ev.payload, dict):
            sleep_after_upload = ev.payload.get("sleep_after_upload")
            if isinstance(sleep_after_upload, bool):
                self._pending_sleep_after_upload = sleep_after_upload

    def cancel_pending_sleep(self) -> None:
        """ユーザー操作によるスリープキャンセル。自動スリープの予約を破棄する。"""
        self._auto_sleep_allowed = False
        self._pending_sleep_after_upload = None
        self._sleep_cancelled_by_user = True
        self.event_bus.publish_domain_event(AutoSleepCancelled())
        self.logger.info("自動スリープをキャンセルしました")

    def reactivate_sleep(self) -> None:
        """ユーザー操作によるスリープ再有効化。"""
        self._sleep_cancelled_by_user = False
        # プロセス完了後に再有効化した場合は通知を再送する
        uc_state = self.start_edit_upload_uc.get_state()
        effective = (
            self.start_edit_upload_uc.get_sleep_after_upload_effective()
        )
        if uc_state in ("succeeded", "failed") and effective:
            self._auto_sleep_allowed = True
            self._pending_sleep_after_upload = effective
            self.event_bus.publish_domain_event(
                AutoSleepPending(
                    timeout_seconds=15.0,
                    message=(
                        "編集・アップロードが完了しました。15秒後に自動スリープします。"
                        "続けて作業する場合はキャンセルしてください。"
                    ),
                    sleep_after_upload=effective,
                )
            )
            self.logger.info("自動スリープを再有効化しました")

    async def start_auto_sleep(self) -> None:
        """自動スリープを開始する。"""
        if not self._auto_sleep_allowed:
            raise RuntimeError("自動スリープが許可されていません")

        self._auto_sleep_allowed = False
        sleep_after_upload = self._pending_sleep_after_upload
        self._pending_sleep_after_upload = None

        self.logger.info("自動スリープを開始します。")
        self.event_bus.publish_domain_event(AutoSleepStarted())
        # スリープ直前にログが残るよう少し待機
        await self._sleep(3)
        await self.power_manager.sleep(sleep_after_upload=sleep_after_upload)
