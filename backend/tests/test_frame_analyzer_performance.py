"""FrameAnalyzer の各メソッドを 1/60 秒 (約16.667ms) 以内に終わるか判定するテスト。

注意:
  - 現状で閾値を超えるメソッド (OCR や複合処理を含む) は Fail になります。
  - ボトルネック特定用のテストとして利用を想定。
  - デフォルトではスキップされます。実行するには: pytest -m perf

"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Awaitable, Callable, Protocol, Sequence

import cv2
import pytest
from splat_replay.domain.models import GameMode  # noqa: E402
from test_frame_analyzer import TEMPLATE_DIR, create_analyzer  # noqa: E402

# ==== 設定 ====
DEFAULT_THRESHOLD_SEC = (
    1.0 / 60.0 / 4.0
)  # 60fpsで1フレーム当たり4つの解析をする想定
THRESHOLD_SEC = float(os.getenv("PERF_THRESHOLD_SEC", DEFAULT_THRESHOLD_SEC))
ITER = 5  # 本計測回数 (平均化用)


@dataclass
class SpeedCase:
    name: str  # 表示名
    method: str  # analyzer のメソッド名
    image: str  # 使用画像
    args: Sequence[object] = ()
    prepare: Callable[..., Awaitable[Sequence[object]]] | None = (
        None  # 動的引数生成
    )
    enabled: bool = True
    threshold_sec: float | None = None  # 個別閾値 (None はグローバル閾値)
    xfail: bool = False  # 現状達成不能な場合 True


class _RateAnalyzer(Protocol):
    async def extract_game_mode(self, frame: object) -> GameMode | None: ...


async def _prepare_extract_rate(
    analyzer: _RateAnalyzer, frame: object
) -> tuple[GameMode, ...]:
    mode = await analyzer.extract_game_mode(frame)
    return (mode,) if mode else (GameMode.BATTLE,)


CASES: list[SpeedCase] = [
    SpeedCase("detect_power_off", "detect_power_off", "power_off.png"),
    SpeedCase(
        "detect_match_select",
        "detect_match_select",
        "match_select_regular.png",
    ),
    SpeedCase(
        "extract_game_mode", "extract_game_mode", "match_select_regular.png"
    ),
    SpeedCase(
        "extract_match_select",
        "extract_match_select",
        "match_select_regular.png",
        args=(GameMode.BATTLE,),
    ),
    SpeedCase(
        "extract_rate",
        "extract_rate",
        "rate_XP1971.9.png",
        prepare=_prepare_extract_rate,
        threshold_sec=0.06,  # OCRも含むので緩和
    ),
    SpeedCase(
        "detect_matching_start", "detect_matching_start", "matching_1.png"
    ),
    SpeedCase(
        "detect_schedule_change",
        "detect_schedule_change",
        "schedule_change_1.png",
    ),
    SpeedCase(
        "detect_session_start",
        "detect_session_start",
        "battle_start_1.png",
        args=(GameMode.BATTLE,),
    ),
    SpeedCase(
        "detect_session_abort",
        "detect_session_abort",
        "battle_abort_1.png",
        args=(GameMode.BATTLE,),
    ),
    SpeedCase(
        "detect_communication_error",
        "detect_communication_error",
        "battle_communication_error_1.png",
        args=(GameMode.BATTLE,),
    ),
    SpeedCase(
        "detect_session_finish",
        "detect_session_finish",
        "battle_finish_1.png",
        args=(GameMode.BATTLE,),
    ),
    SpeedCase(
        "detect_session_finish_end",
        "detect_session_finish_end",
        "battle_judgement_1.png",
        args=(GameMode.BATTLE,),
    ),
    SpeedCase(
        "detect_session_judgement",
        "detect_session_judgement",
        "battle_judgement_1.png",
        args=(GameMode.BATTLE,),
    ),
    SpeedCase(
        "extract_session_judgement",
        "extract_session_judgement",
        "battle_judgement_1.png",
        args=(GameMode.BATTLE,),
    ),
    SpeedCase("detect_loading", "detect_loading", "loading_1.png"),
    SpeedCase("detect_loading_end", "detect_loading_end", "power_off.png"),
    SpeedCase(
        "detect_session_result",
        "detect_session_result",
        "battle_result_1.png",
        args=(GameMode.BATTLE,),
    ),
    SpeedCase(
        "extract_session_result",
        "extract_session_result",
        "battle_result_1.png",
        args=(GameMode.BATTLE,),
        threshold_sec=0.5,  # OCRも含むので緩和
    ),
]


@pytest.mark.perf
@pytest.mark.asyncio
@pytest.mark.parametrize("case", CASES, ids=[c.name for c in CASES])
async def test_speed_threshold(
    case: SpeedCase, request: pytest.FixtureRequest, perf_recorder
):
    if not case.enabled:
        pytest.skip("disabled")

    analyzer = create_analyzer()

    # 画像ロード
    img_path = TEMPLATE_DIR / case.image
    frame = cv2.imread(str(img_path))
    if frame is None:
        pytest.skip(f"画像読み込み失敗: {img_path}")

    # 動的引数
    args = list(case.args)
    if case.prepare:
        dyn = await case.prepare(analyzer, frame)
        if dyn:
            args = list(dyn)

    method = getattr(analyzer, case.method)

    times: list[float] = []
    for _ in range(ITER):
        start = time.perf_counter()
        if args:
            await method(frame, *args)
        else:
            await method(frame)
        times.append(time.perf_counter() - start)

    avg = sum(times) / len(times)

    # 判定 (個別閾値優先)
    thr = (
        case.threshold_sec if case.threshold_sec is not None else THRESHOLD_SEC
    )
    # perf recorder への記録 (ms)
    perf_recorder(
        {
            "name": case.name,
            "nodeid": request.node.nodeid,
            "avg_ms": avg * 1000.0,
            "thr_ms": thr * 1000.0,
            "runs_ms": [t * 1000.0 for t in times],
        }
    )

    if avg > thr:
        if case.xfail:
            pytest.xfail(
                f"{case.name}: avg={avg * 1000:.3f}ms > threshold={thr * 1000:.3f}ms (expected slow)"
            )
        else:
            pytest.fail(
                f"{case.name}: avg={avg * 1000:.3f}ms > threshold={thr * 1000:.3f}ms (runs={times})"
            )
