"""Switch の動画保存通知を一回ずつにまとめる。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

SwitchCaptureStatus = Literal["saving", "saved"]


@dataclass(frozen=True)
class SwitchCaptureTracker:
    """保存中と完了表示を同一操作として扱う。"""

    status: SwitchCaptureStatus | None = None
    absent_frames: int = 0

    def observe(
        self, status: SwitchCaptureStatus | None
    ) -> tuple[SwitchCaptureTracker, bool]:
        """更新状態と、新しい保存操作を検出したかを返す。"""
        if status is None:
            # shortcut: 非表示2フレームで再受付する。連続操作の実映像で再調整する。
            absent = min(self.absent_frames + 1, 2)
            return SwitchCaptureTracker(
                self.status if absent < 2 else None, absent
            ), False
        return SwitchCaptureTracker(status), (
            status == "saving" and self.status != "saving"
        )
