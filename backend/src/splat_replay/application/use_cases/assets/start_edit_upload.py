"""編集・アップロード開始ユースケース。"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from splat_replay.application.interfaces import LoggerPort
    from splat_replay.application.services import AutoEditor, AutoUploader


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
        logger: LoggerPort,
    ) -> None:
        self._editor = editor
        self._uploader = uploader
        self._logger = logger
        self._task: asyncio.Task[None] | None = None

    async def execute(self) -> None:
        """編集・アップロード処理を開始。

        Raises:
            RuntimeError: 既に実行中の場合
        """
        # 実行中チェック
        if self._task is not None and not self._task.done():
            raise RuntimeError("編集・アップロード処理が既に実行中です")

        # バックグラウンドタスクとして起動
        self._task = asyncio.create_task(self._run_edit_upload())
        self._logger.info("編集・アップロード処理を開始しました")

    async def _run_edit_upload(self) -> None:
        """編集→アップロードを順次実行（内部メソッド）。"""
        try:
            await self._editor.execute()
            await self._uploader.execute()
            self._logger.info("編集・アップロード処理が完了しました")
        except Exception as e:
            self._logger.error(f"編集・アップロード処理中にエラーが発生: {e}")
            raise
