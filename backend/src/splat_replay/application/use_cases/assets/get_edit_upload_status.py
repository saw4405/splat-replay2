"""編集・アップロード状態取得ユースケース。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from splat_replay.application.dto import EditUploadStatusDTO
from splat_replay.application.use_cases.assets.start_edit_upload import (
    StartEditUploadUseCase,
)

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
        start_edit_upload_uc: StartEditUploadUseCase,
    ) -> None:
        self._editor = editor
        self._uploader = uploader
        self._logger = logger
        self._start_edit_upload_uc = start_edit_upload_uc

    async def execute(self) -> EditUploadStatusDTO:
        """編集・アップロード状態を取得。

        Returns:
            EditUploadStatusDTO
        """
        # AutoEditorから進捗を取得
        editor_status = self._editor.get_status()
        progress = editor_status.get("progress", 0)

        # StartEditUploadUseCase の状態を優先する
        if self._start_edit_upload_uc.is_running():
            state = "running"
        else:
            state = self._start_edit_upload_uc.get_state()
            if state == "running":
                state = "idle"
        message = self._start_edit_upload_uc.get_message()

        return EditUploadStatusDTO(
            state=state,
            message=str(message),
            progress=progress if isinstance(progress, int) else 0,
        )
