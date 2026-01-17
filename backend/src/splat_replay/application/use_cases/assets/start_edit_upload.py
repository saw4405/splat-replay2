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

    async def execute(self, *, trigger: EditUploadTrigger = "manual") -> None:
        """編集・アップロード処理を開始。

        Raises:
            RuntimeError: 既に実行中の場合
        """
        # 実行中チェック
        if self._task is not None and not self._task.done():
            raise RuntimeError("編集・アップロード処理が既に実行中です")

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
            self._state = "failed"
            self._message = f"編集・アップロード処理に失敗しました: {e}"
            self._logger.error(f"編集・アップロード処理中にエラーが発生: {e}")
            self._event_bus.publish_domain_event(
                EditUploadCompleted(
                    success=False,
                    message=str(e),
                    trigger=trigger,
                )
            )
            self._schedule_auto_sleep(trigger)
            raise

        self._event_bus.publish_domain_event(
            EditUploadCompleted(
                success=True,
                message="編集・アップロード処理が完了しました",
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

    def _schedule_auto_sleep(self, trigger: EditUploadTrigger) -> None:
        if trigger != "manual":
            return
        settings = self._config.get_behavior_settings()
        if not settings.sleep_after_upload:
            return
        self._event_bus.publish_domain_event(
            AutoSleepPending(
                timeout_seconds=15.0,
                message=(
                    "編集・アップロードが完了しました。15秒後に自動スリープします。"
                    "続けて作業する場合はキャンセルしてください。"
                ),
            )
        )
