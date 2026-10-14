"""必須セットアップ判定の出力とキャッシュポート。"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class RequiredSetupIssue:
    """アプリ利用前に解消が必要な設定不足。"""

    code: str
    step: str
    substep_id: str
    message: str


class RequiredSetupIssueCachePort(Protocol):
    """必須設定結果の短命なプロセス内キャッシュ。"""

    def get_or_compute(
        self,
        compute: Callable[[], list[RequiredSetupIssue]],
        *,
        force_refresh: bool = False,
    ) -> tuple[RequiredSetupIssue, ...]: ...

    def invalidate(self) -> None: ...

    def run_repair_action(
        self,
        action: Callable[[], bool],
        *,
        only_once: bool,
    ) -> bool:
        """修復先の保存を排他実行し、初回status案内を一度だけ許可する。"""
        ...
