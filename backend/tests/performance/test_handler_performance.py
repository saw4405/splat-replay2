"""Handler performance regression tests.

これらのテストは、30fps 処理予算に安全係数を加えた閾値で
handler の性能回帰を検出します。
デフォルトではスキップされます。

実行方法:
    pytest -m perf -v -s
"""

from __future__ import annotations

import sys
import time
from collections.abc import Callable, Mapping, Set
from dataclasses import replace
from pathlib import Path
from typing import Optional, cast

import cv2
import numpy as np
import pytest

pytestmark = pytest.mark.perf

tests_dir = Path(__file__).resolve().parents[1]
if str(tests_dir) not in sys.path:
    sys.path.insert(0, str(tests_dir))

from logic.domain.test_frame_analyzer import (  # noqa: E402
    TEMPLATE_DIR,
    create_analyzer,
)

from splat_replay.application.interfaces import (  # noqa: E402
    EventBusPort,
    LoggerPort,
    WeaponRecognitionPort,
    WeaponRecognitionResult,
    WeaponSlotResult,
)
from splat_replay.application.interfaces.messaging import (  # noqa: E402
    EventSubscription,
)
from splat_replay.application.services.recording.ingame_handler import (  # noqa: E402
    InGamePhaseHandler,
)
from splat_replay.application.services.recording.recording_context import (
    RecordingContext,
)
from splat_replay.application.services.recording.weapon_detection_service import (
    WeaponDetectionService,
)
from splat_replay.domain.events import DomainEvent  # noqa: E402
from splat_replay.domain.services import RecordState  # noqa: E402

FRAME_BUDGET_SEC = 1.0 / 30.0
FRAME_BUDGET_SAFETY_FACTOR = 2.0
THRESHOLD_SEC = FRAME_BUDGET_SEC * FRAME_BUDGET_SAFETY_FACTOR
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
    def request_cancel(self) -> None:
        pass

    async def detect_weapon_display(self, frame: np.ndarray) -> bool:
        return False

    async def recognize_weapons(
        self,
        frame: np.ndarray,
        save_predict_weapons_output: bool = True,
        target_slots: set[str] | None = None,
        previous_results: dict[str, WeaponSlotResult] | None = None,
        battle_dir_name: str | None = None,
    ) -> WeaponRecognitionResult:
        _ = save_predict_weapons_output
        _ = target_slots
        _ = previous_results
        _ = battle_dir_name
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
    """InGamePhaseHandler.handle() が録画中の処理予算内に収まることを確認する。"""
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
    print(
        f"\n{name}: avg={avg * 1000:.3f}ms (threshold={THRESHOLD_SEC * 1000:.3f}ms)"
    )
    assert avg <= THRESHOLD_SEC, (
        f"Performance check failed: avg={avg * 1000:.3f}ms "
        f"exceeded threshold={THRESHOLD_SEC * 1000:.3f}ms"
    )
