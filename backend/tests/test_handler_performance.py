"""Handler performance measurement tests.

これらのテストは性能測定を行いますが、アサートはしません（任意実行）。
測定結果を出力して、パフォーマンスの追跡・改善の参考にします。
デフォルトではスキップされます。

実行方法:
    pytest -m perf -v -s
"""

from __future__ import annotations

import time
from dataclasses import replace
from typing import Callable, Mapping, Optional, Set, cast

import cv2
import numpy as np
import pytest
from splat_replay.application.interfaces import (
    EventBusPort,  # noqa: E402
    LoggerPort,
    WeaponRecognitionPort,
)
from splat_replay.application.interfaces.messaging import EventSubscription  # noqa: E402
from splat_replay.application.services.recording.ingame_handler import (
    InGamePhaseHandler,
)  # noqa: E402
from splat_replay.application.services.recording.recording_context import (
    RecordingContext,
)  # noqa: E402
from splat_replay.application.services.recording.weapon_detection_service import (
    WeaponDetectionService,
)  # noqa: E402
from splat_replay.application.interfaces import WeaponRecognitionResult  # noqa: E402
from splat_replay.domain.events import DomainEvent  # noqa: E402
from splat_replay.domain.services import RecordState  # noqa: E402

# Reuse analyzer factory and template dir from analyzer tests
from test_frame_analyzer import TEMPLATE_DIR, create_analyzer  # noqa: E402

# ハンドラーの handle は 1/60 秒以内を目標値とする
THRESHOLD_SEC = 1.0 / 60.0
ITER = 5


class _DummyLogger:
    def debug(self, event: str, **kw: object) -> None:
        return None

    def info(self, event: str, **kw: object) -> None:
        return None

    def warning(self, event: str, **kw: object) -> None:
        return None

    def error(self, event: str, **kw: object) -> None:
        return None

    def exception(self, event: str, **kw: object) -> None:
        return None


class _DummySubscription:
    def poll(self, max_items: int = 100) -> list[object]:
        return []

    def close(self) -> None:
        return None


class _DummyBus:
    def publish(
        self, event_type: str, payload: Mapping[str, object] | None = None
    ) -> None:
        return None

    def publish_domain_event(self, event: DomainEvent) -> None:
        return None

    def subscribe(
        self, event_types: Optional[Set[str]] = None
    ) -> EventSubscription:
        return _DummySubscription()


class _DummyWeaponRecognizer:
    async def detect_weapon_display(self, frame: np.ndarray) -> bool:
        return False

    async def recognize_weapons(
        self,
        frame: np.ndarray,
        save_unmatched_report: bool = True,
    ) -> WeaponRecognitionResult:
        raise RuntimeError("not used")


@pytest.fixture()
def handler() -> InGamePhaseHandler:
    analyzer = create_analyzer()
    logger = _DummyLogger()
    bus = _DummyBus()
    weapon_detection_service = WeaponDetectionService(
        cast(WeaponRecognitionPort, _DummyWeaponRecognizer()),
        cast(LoggerPort, logger),
        cast(EventBusPort, bus),
    )
    return InGamePhaseHandler(
        analyzer,
        cast(LoggerPort, logger),
        cast(EventBusPort, bus),
        weapon_detection_service,
    )


@pytest.fixture()
def load_image() -> Callable[[str], np.ndarray]:
    def _load(filename: str) -> np.ndarray:
        image_path = TEMPLATE_DIR / filename
        image = cv2.imread(str(image_path))
        if image is None:
            pytest.skip(
                f"画像ファイルが存在しないか読み込めません: {image_path}"
            )
        return image

    return _load


@pytest.mark.perf
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "name, filename, ctx_modifier",
    [
        (
            "early_abort",
            "battle_abort_1.png",
            lambda ctx: replace(ctx, battle_started_at=time.time() - 10),
        ),
        (
            "finish",
            "battle_finish_1.png",
            lambda ctx: replace(ctx, battle_started_at=time.time() - 120),
        ),
        (
            "communication_error",
            "battle_communication_error_1.png",
            lambda ctx: replace(ctx, battle_started_at=time.time() - 120),
        ),
        (
            "none",
            "loading_1.png",
            lambda ctx: replace(ctx, battle_started_at=time.time() - 120),
        ),
        (
            "time_limit",
            "battle_start_1.png",
            lambda ctx: replace(ctx, battle_started_at=time.time() - 601),
        ),
    ],
)
async def test_ingame_handler_handle_performance(
    handler: InGamePhaseHandler,
    load_image: Callable[[str], np.ndarray],
    name: str,
    filename: str,
    ctx_modifier: Callable[[RecordingContext], RecordingContext],
) -> None:
    """InGamePhaseHandler.handle() の性能を測定（アサートなし）。"""
    frame = load_image(filename)
    ctx = RecordingContext()
    ctx = ctx_modifier(ctx)
    state = RecordState.RECORDING

    times: list[float] = []
    for _ in range(ITER):
        start = time.perf_counter()
        await handler.handle(frame=frame, ctx=ctx, state=state)
        times.append(time.perf_counter() - start)

    avg = sum(times) / len(times)
    # アサートせず、測定結果のみ出力
    print(
        f"\n{name}: avg={avg * 1000:.3f}ms (threshold={THRESHOLD_SEC * 1000:.3f}ms)"
    )
