"""Recording services.

Phase handlers for recording session - Base protocol and registry.
Phase 4 Step 1: フェーズ別処理を独立クラスに抽出。
Strategy Pattern を使用して各フェーズのロジックを分離。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from splat_replay.domain.models import Frame
from splat_replay.application.services.recording.auto_recorder import (
    AutoRecorder,
)
from splat_replay.application.services.recording.recording_preparation import (
    RecordingPreparationService,
)

__all__ = [
    "AutoRecorder",
    "RecordingPreparationService",
    "PhaseHandler",
]

if TYPE_CHECKING:
    from splat_replay.application.services.recording.recording_context import (
        RecordingContext,
    )


class PhaseHandler(Protocol):
    """フェーズ別処理のプロトコル。"""

    async def handle(
        self, frame: Frame, ctx: RecordingContext
    ) -> RecordingContext:
        """フレームを処理する。

        Args:
            frame: 処理対象のフレーム
            ctx: 録画コンテキスト（状態・メタデータを含む）

        Returns:
            更新されたコンテキスト（不変性を保持するため新しいインスタンス）
        """
        ...
