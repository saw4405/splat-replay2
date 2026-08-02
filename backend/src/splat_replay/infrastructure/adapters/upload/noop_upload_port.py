"""no-op のアップロードアダプタ。"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, List, Optional
import time

from structlog.stdlib import BoundLogger

from splat_replay.application.interfaces import (
    Caption,
    PrivacyStatus,
    UploadPort,
)


class NoOpUploadPort(UploadPort):
    """E2E 実行時にアップロードを無効化するための実装。"""

    def __init__(self, logger: BoundLogger) -> None:
        self.logger = logger

    def upload(
        self,
        path: Path,
        title: str,
        description: str,
        tags: List[str] = [],
        privacy_status: PrivacyStatus = "private",
        thumb: Optional[Path] = None,
        caption: Optional[Caption] = None,
        playlist_id: str = "",
        progress_callback: Optional[Callable[[float], None]] = None,
    ) -> None:
        """外部通信を行わず、呼び出し内容だけを記録し、進捗をシミュレートする。"""
        _ = description, tags
        self.logger.info(
            "E2E no-op upload: upload skipped",
            path=str(path),
            title=title,
            privacy_status=privacy_status,
            has_thumbnail=thumb is not None,
            has_caption=caption is not None,
            playlist_id=playlist_id,
        )

        if progress_callback:
            # 0%から100%まで10%刻みで進捗をシミュレート（約1秒）
            for p in range(0, 101, 10):
                progress_callback(float(p))
                time.sleep(0.1)
