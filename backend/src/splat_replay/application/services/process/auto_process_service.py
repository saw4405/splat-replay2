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
    AssetRecordedSaved,
    AutoProcessPending,
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
        self._scan_generation = 0
        self._handled_generation = 0
        self._cancelled_generation = 0
        self._not_before: dict[int, float] = {}
        self._scan_wakeup = asyncio.Event()
        self._worker_task: asyncio.Task[None] | None = None
        self._sleep_generation = 0
        self._sleep_task: asyncio.Task[None] | None = None
        self.update_pending = False
        self.power_off_count = 0

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
                AssetRecordedSaved.EVENT_TYPE,
            }
        )
        self.logger.info("AutoProcessService started")
        self._worker_task = asyncio.create_task(self._run_scan_worker())
        if self._has_pending_assets():
            self.logger.info(
                "起動時に未処理動画を検出しました。録画を優先するため自動処理は開始しません"
            )

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
                    elif ev.type == AssetRecordedSaved.EVENT_TYPE:
                        if (
                            self._is_auto_processing
                            and self.start_edit_upload_uc.get_state()
                            not in ("cancelling", "cancelled")
                        ):
                            self._request_scan(delay_seconds=0.0)

                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            self.logger.info("AutoProcessService stopped")
            raise
        finally:
            sub.close()
            sleep_task = self._cancel_sleep_task()
            if sleep_task is not None:
                try:
                    await sleep_task
                except asyncio.CancelledError:
                    pass
            worker_task = self._worker_task
            self._worker_task = None
            if worker_task is not None:
                worker_task.cancel()
                try:
                    await worker_task
                except asyncio.CancelledError:
                    pass

    async def handle_power_off_detected(self, event: object) -> None:
        """電源OFF検出時の処理。"""
        ev = cast(Any, event)
        is_final = False
        if hasattr(ev, "payload") and isinstance(ev.payload, dict):
            is_final = bool(ev.payload.get("final", False))
        if not is_final:
            return
        self.power_off_count += 1

        settings = self.config.get_behavior_settings()
        if not settings.edit_after_power_off:
            return

        if not self._has_pending_assets() and not self._is_auto_processing:
            self.logger.info(
                "未処理動画がないため自動処理要求をスキップします"
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
        self._request_scan(delay_seconds=timeout_seconds)

    def _has_pending_assets(self) -> bool:
        return bool(self.repo.list_recordings() or self.repo.list_edited())

    def is_idle(self) -> bool:
        """猶予中の後処理も含め、実行すべき要求が完了しているか。"""
        return (
            self._handled_generation >= self._scan_generation
            and not self._is_auto_processing
            and not self.start_edit_upload_uc.is_running()
        )

    def _pending_asset_ids(self) -> frozenset[str]:
        recorded = (str(asset.video) for asset in self.repo.list_recordings())
        edited = (str(path) for path in self.repo.list_edited())
        return frozenset((*recorded, *edited))

    def _request_scan(self, *, delay_seconds: float) -> int:
        self._scan_generation += 1
        generation = self._scan_generation
        self._not_before[generation] = (
            asyncio.get_running_loop().time() + delay_seconds
        )
        self._scan_wakeup.set()
        return generation

    async def _run_scan_worker(self) -> None:
        """generationを失わず、未処理ファイルを単一workerで走査する。"""
        while True:
            await self._scan_wakeup.wait()
            self._scan_wakeup.clear()

            while self._handled_generation < self._scan_generation:
                generation = self._scan_generation
                if generation <= self._cancelled_generation:
                    self._mark_generation_handled(generation)
                    break

                not_before = self._not_before.get(generation, 0.0)
                remaining = not_before - asyncio.get_running_loop().time()
                if remaining > 0:
                    try:
                        await asyncio.wait_for(
                            self._scan_wakeup.wait(), timeout=remaining
                        )
                    except asyncio.TimeoutError:
                        pass
                    else:
                        self._scan_wakeup.clear()
                        continue

                if generation <= self._cancelled_generation:
                    self._mark_generation_handled(generation)
                    continue

                before = self._pending_asset_ids()
                if not before:
                    self._mark_generation_handled(generation)
                    continue

                execution_state = "failed"
                try:
                    await self.start_auto_process()
                    await self.start_edit_upload_uc.wait_until_complete()
                    execution_state = self.start_edit_upload_uc.get_state()
                except Exception as exc:  # noqa: BLE001
                    self.logger.error(
                        "自動編集・アップロードworkerが失敗しました",
                        error=str(exc),
                    )
                finally:
                    self._is_auto_processing = False

                self._mark_generation_handled(generation)
                after = self._pending_asset_ids()
                added_during_run = after - before
                if execution_state == "cancelled":
                    break
                if self._scan_generation > generation or (
                    execution_state == "succeeded" and bool(added_during_run)
                ):
                    if self._scan_generation == generation:
                        self._request_scan(delay_seconds=0.0)
                    continue

                # 失敗して残った同じファイルは、次の外部要求か再起動まで
                # 即時再試行しない。
                break

    def _mark_generation_handled(self, generation: int) -> None:
        """統合済みgenerationまでの猶予時刻を破棄する。"""
        self._handled_generation = generation
        for handled in tuple(self._not_before):
            if handled <= generation:
                self._not_before.pop(handled, None)

    def cancel_pending_process(self) -> None:
        """猶予中の自動処理要求を取り消す。"""
        self._cancelled_generation = self._scan_generation
        self._scan_wakeup.set()
        self.logger.info("待機中の自動編集・アップロードをキャンセルしました")

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
        timeout_seconds = 0.0
        ev = cast(Any, event_obj)
        if hasattr(ev, "payload") and isinstance(ev.payload, dict):
            sleep_after_upload = ev.payload.get("sleep_after_upload")
            if isinstance(sleep_after_upload, bool):
                self._pending_sleep_after_upload = sleep_after_upload
            timeout_value = ev.payload.get("timeout_seconds")
            if isinstance(timeout_value, (int, float)):
                timeout_seconds = max(0.0, float(timeout_value))
        self._schedule_auto_sleep(timeout_seconds=timeout_seconds)

    def _schedule_auto_sleep(self, *, timeout_seconds: float) -> None:
        """ブラウザに依存しない自動スリープ猶予タスクを予約する。"""
        self._sleep_generation += 1
        generation = self._sleep_generation
        self._cancel_sleep_task()
        self._sleep_task = asyncio.create_task(
            self._run_pending_sleep(
                generation=generation,
                timeout_seconds=timeout_seconds,
            )
        )

    async def _run_pending_sleep(
        self, *, generation: int, timeout_seconds: float
    ) -> None:
        try:
            await self._sleep(timeout_seconds)
            if (
                generation != self._sleep_generation
                or not self._auto_sleep_allowed
                or self._sleep_cancelled_by_user
            ):
                return
            await self.start_auto_sleep()
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            self.logger.error(
                "自動スリープの実行に失敗しました",
                error=str(exc),
            )
        finally:
            if self._sleep_task is asyncio.current_task():
                self._sleep_task = None

    def _cancel_sleep_task(self) -> asyncio.Task[None] | None:
        task = self._sleep_task
        self._sleep_task = None
        if task is not None and not task.done():
            task.cancel()
        return task

    def cancel_pending_sleep(self) -> None:
        """ユーザー操作によるスリープキャンセル。自動スリープの予約を破棄する。"""
        self._sleep_generation += 1
        self._cancel_sleep_task()
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
        if self.update_pending:
            return
        if not self._auto_sleep_allowed:
            raise RuntimeError("自動スリープが許可されていません")

        self._auto_sleep_allowed = False
        sleep_after_upload = self._pending_sleep_after_upload
        self._pending_sleep_after_upload = None

        self.logger.info("自動スリープを開始します。")
        self.event_bus.publish_domain_event(AutoSleepStarted())
        # スリープ直前にログが残るよう少し待機
        await self._sleep(3)
        if self.update_pending:
            return
        await self.power_manager.sleep(sleep_after_upload=sleep_after_upload)
