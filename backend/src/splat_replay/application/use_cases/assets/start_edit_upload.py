"""編集・アップロード開始ユースケース。"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Literal

from splat_replay.application.dto.assets import EditUploadState
from splat_replay.application.interfaces import (
    ConfigPort,
    EventBusPort,
    LoggerPort,
)
from splat_replay.domain.events import AutoSleepPending, EditUploadCompleted

if TYPE_CHECKING:
    from splat_replay.application.services import AutoEditor, AutoUploader


EditUploadTrigger = Literal["auto", "manual"]


class StartEditUploadUseCase:
    """編集・アップロード処理を開始するユースケース。

    責務：
    - 編集・アップロードタスクをバックグラウンドで開始
    - 実行中の重複起動を防止
    """

    def __init__(
        self,
        editor: AutoEditor,
        uploader: AutoUploader,
        event_bus: EventBusPort,
        config: ConfigPort,
        logger: LoggerPort,
    ) -> None:
        self._editor = editor
        self._uploader = uploader
        self._event_bus = event_bus
        self._config = config
        self._logger = logger
        self._task: asyncio.Task[None] | None = None
        self._state: EditUploadState = "idle"
        self._message: str = ""
        self._sleep_after_upload_default = False
        self._sleep_after_upload_effective = False

    async def execute(self, *, trigger: EditUploadTrigger = "manual") -> None:
        """編集・アップロード処理を開始。

        Raises:
            RuntimeError: 既に実行中の場合
        """
        # 実行中チェック
        if self._task is not None and not self._task.done():
            raise RuntimeError("編集・アップロード処理が既に実行中です")

        self._reset_runtime_options()
        self._state = "running"
        self._message = "編集・アップロード処理を開始しました"
        # バックグラウンドタスクとして起動
        self._task = asyncio.create_task(self._run_edit_upload(trigger))
        self._logger.info("編集・アップロード処理を開始しました")

    def is_running(self) -> bool:
        """編集・アップロードが実行中かどうかを返す。"""
        return self._task is not None and not self._task.done()

    async def _run_edit_upload(self, trigger: EditUploadTrigger) -> None:
        """編集→アップロードを順次実行（内部メソッド）。"""
        try:
            await self._editor.execute()
            await self._uploader.execute()
            self._state = "succeeded"
            self._message = "編集・アップロード処理が完了しました"
            self._logger.info("編集・アップロード処理が完了しました")
        except Exception as e:
            sleep_after_upload = self.get_sleep_after_upload_effective()
            self._state = "failed"
            self._message = f"編集・アップロード処理に失敗しました: {e}"
            self._logger.error(f"編集・アップロード処理中にエラーが発生: {e}")
            self._event_bus.publish_domain_event(
                EditUploadCompleted(
                    success=False,
                    message=str(e),
                    sleep_after_upload=sleep_after_upload,
                    trigger=trigger,
                )
            )
            self._schedule_auto_sleep(trigger)
            raise

        sleep_after_upload = self.get_sleep_after_upload_effective()
        self._event_bus.publish_domain_event(
            EditUploadCompleted(
                success=True,
                message="編集・アップロード処理が完了しました",
                sleep_after_upload=sleep_after_upload,
                trigger=trigger,
            )
        )
        self._schedule_auto_sleep(trigger)

    def get_state(self) -> EditUploadState:
        """現在の状態を取得する。"""
        return self._state

    def get_message(self) -> str:
        """現在の状態メッセージを取得する。"""
        return self._message

    def update_sleep_after_upload(self, enabled: bool) -> None:
        """今回の処理に限ったスリープ設定を更新する。"""
        if not self.is_running():
            raise RuntimeError(
                "編集中またはアップロード中の処理がないため変更できません"
            )

        self._sleep_after_upload_effective = enabled
        self._logger.info(
            "編集・アップロード処理の一時スリープ設定を更新しました",
            sleep_after_upload=enabled,
        )

    def get_sleep_after_upload_default(self) -> bool:
        """保存済み設定の既定値を返す。"""
        default, _, _ = self._resolve_sleep_after_upload_state()
        return default

    def get_sleep_after_upload_effective(self) -> bool:
        """今回の処理で有効なスリープ設定を返す。"""
        _, effective, _ = self._resolve_sleep_after_upload_state()
        return effective

    def is_sleep_after_upload_overridden(self) -> bool:
        """今回の処理で一時上書き中かどうかを返す。"""
        _, _, overridden = self._resolve_sleep_after_upload_state()
        return overridden

    def _reset_runtime_options(self) -> None:
        settings = self._config.get_behavior_settings()
        self._sleep_after_upload_default = settings.sleep_after_upload
        self._sleep_after_upload_effective = settings.sleep_after_upload

    def _resolve_sleep_after_upload_state(self) -> tuple[bool, bool, bool]:
        if self._state == "idle":
            default = self._config.get_behavior_settings().sleep_after_upload
            return default, default, False

        default = self._sleep_after_upload_default
        effective = self._sleep_after_upload_effective
        return default, effective, effective != default

    def _schedule_auto_sleep(self, trigger: EditUploadTrigger) -> None:
        if trigger != "manual":
            return
        sleep_after_upload = self.get_sleep_after_upload_effective()
        if not sleep_after_upload:
            return
        self._event_bus.publish_domain_event(
            AutoSleepPending(
                timeout_seconds=15.0,
                message=(
                    "編集・アップロードが完了しました。15秒後に自動スリープします。"
                    "続けて作業する場合はキャンセルしてください。"
                ),
                sleep_after_upload=sleep_after_upload,
            )
        )
