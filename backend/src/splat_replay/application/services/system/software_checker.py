"""ソフトウェアチェッカーの抽象化。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from splat_replay.application.services.setup.system_check_service import (
        SoftwareCheckResult,
    )


class SoftwareChecker(Protocol):
    """ソフトウェアのインストール状態をチェックするインターフェース。"""

    def check(self) -> SoftwareCheckResult:
        """ソフトウェアのインストール状態を確認する。

        Returns:
            チェック結果
        """
        ...
