"""アップロードユースケース。"""

from __future__ import annotations

from splat_replay.application.services import AutoEditor, AutoUploader


class UploadUseCase:
    """自動編集と自動アップロードのみ実行するユースケース。"""

    def __init__(self, editor: AutoEditor, uploader: AutoUploader) -> None:
        self.editor = editor
        self.uploader = uploader

    async def execute(self) -> None:
        """動画編集とアップロードを行う。"""
        import asyncio

        await asyncio.to_thread(self.editor.execute)
        await asyncio.to_thread(self.uploader.execute)
