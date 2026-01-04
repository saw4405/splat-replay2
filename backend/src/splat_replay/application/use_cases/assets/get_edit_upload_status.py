"""編集・アップロード状態取得ユースケース。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from splat_replay.application.dto import EditUploadStatusDTO

if TYPE_CHECKING:
    from splat_replay.application.interfaces import LoggerPort
    from splat_replay.application.services import AutoEditor, AutoUploader


class GetEditUploadStatusUseCase:
    """編集・アップロード処理の状態を取得するユースケース。

    責務：
    - AutoEditor と AutoUploader の状態を取得
    - EditUploadStatusDTO に変換
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

    async def execute(self) -> EditUploadStatusDTO:
        """編集・アップロード状態を取得。

        Returns:
            EditUploadStatusDTO
        """
        # AutoEditorから状態を取得
        editor_status = self._editor.get_status()
        is_running = editor_status.get("is_running", False)
        message = editor_status.get("message", "")
        progress = editor_status.get("progress", 0)

        # 状態を文字列に変換
        if is_running:
            state = "running"
        elif progress == 100:
            state = "succeeded"
        else:
            state = "idle"

        return EditUploadStatusDTO(
            state=state,
            message=str(message),
            progress=progress if isinstance(progress, int) else 0,
        )
