"""必須設定キャッシュのinvalidate直列化を確認する。"""

from __future__ import annotations

from threading import Event, Thread

from splat_replay.application.interfaces import RequiredSetupIssue
from splat_replay.infrastructure.adapters.system.required_setup_issue_cache import (
    InMemoryRequiredSetupIssueCache,
)


def test_invalidate_waits_for_inflight_check_and_drops_its_result() -> None:
    cache = InMemoryRequiredSetupIssueCache()
    computation_started = Event()
    release_computation = Event()
    old_issue = RequiredSetupIssue(
        code="old",
        step="ffmpeg_setup",
        substep_id="ffmpeg-download-extract",
        message="old",
    )
    new_issue = RequiredSetupIssue(
        code="new",
        step="ffmpeg_setup",
        substep_id="ffmpeg-download-extract",
        message="new",
    )
    returned: list[tuple[RequiredSetupIssue, ...]] = []

    def slow_check() -> list[RequiredSetupIssue]:
        computation_started.set()
        assert release_computation.wait(timeout=2)
        return [old_issue]

    getter = Thread(
        target=lambda: returned.append(cache.get_or_compute(slow_check))
    )
    getter.start()
    assert computation_started.wait(timeout=2)

    invalidator = Thread(target=cache.invalidate)
    invalidator.start()
    release_computation.set()
    getter.join(timeout=2)
    invalidator.join(timeout=2)

    assert not getter.is_alive()
    assert not invalidator.is_alive()
    assert returned == [(old_issue,)]
    assert cache.get_or_compute(lambda: [new_issue]) == (new_issue,)


def test_legacy_repair_claim_is_once_per_cache_lifetime() -> None:
    cache = InMemoryRequiredSetupIssueCache()

    assert cache.run_repair_action(lambda: True, only_once=True) is True
    cache.invalidate()
    assert cache.run_repair_action(lambda: True, only_once=True) is False


def test_explicit_repair_selection_is_serialized_and_claims_status_repair() -> (
    None
):
    cache = InMemoryRequiredSetupIssueCache()
    actions: list[str] = []

    assert (
        cache.run_repair_action(
            lambda: actions.append("selected") or True,
            only_once=False,
        )
        is True
    )
    assert (
        cache.run_repair_action(
            lambda: actions.append("status") or True,
            only_once=True,
        )
        is False
    )
    assert actions == ["selected"]
