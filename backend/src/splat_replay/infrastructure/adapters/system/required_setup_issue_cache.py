"""必須設定判定の短命なプロセス内キャッシュ。"""

from __future__ import annotations

from collections.abc import Callable
from threading import RLock

from splat_replay.application.interfaces import (
    RequiredSetupIssue,
    RequiredSetupIssueCachePort,
)


class InMemoryRequiredSetupIssueCache(RequiredSetupIssueCachePort):
    """検査とinvalidateを同じlockで直列化する小さなcache adapter。"""

    def __init__(self) -> None:
        self._lock = RLock()
        self._issues: tuple[RequiredSetupIssue, ...] | None = None
        self._legacy_repair_claimed = False

    def get_or_compute(
        self,
        compute: Callable[[], list[RequiredSetupIssue]],
        *,
        force_refresh: bool = False,
    ) -> tuple[RequiredSetupIssue, ...]:
        with self._lock:
            if self._issues is None or force_refresh:
                self._issues = tuple(compute())
            return self._issues

    def invalidate(self) -> None:
        with self._lock:
            self._issues = None

    def run_repair_action(
        self,
        action: Callable[[], bool],
        *,
        only_once: bool,
    ) -> bool:
        """修復先更新をcache計算/invalidateと直列化する。"""
        with self._lock:
            if only_once and self._legacy_repair_claimed:
                return False
            applied = action()
            if applied:
                self._legacy_repair_claimed = True
            return applied
