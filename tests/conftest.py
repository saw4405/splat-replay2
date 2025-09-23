from __future__ import annotations

import time
from typing import Callable, List, Optional, Sequence, TypedDict

import pytest

# オプション名: --case-time を指定すると各テスト (call フェーズ) の実行時間を逐次表示


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("timing")
    group.addoption(
        "--case-time",
        action="store_true",
        dest="case_time",
        help="Print each test case execution time immediately after it runs.",
    )
    group.addoption(
        "--perf-avg",
        action="store_true",
        dest="perf_avg",
        help=(
            "Collect and print average timings for performance tests (requires test to use perf_recorder fixture)."
        ),
    )


# 各テストケース単位 (call フェーズ) の経過時間を測るため report から start/stop を抽出
# setup/teardown も測りたい場合は pytest_runtest_protocol を独自実装する手もある

_start_times: dict[str, float] = {}
_case_time_enabled: bool = False
_perf_avg_enabled: bool = False


class PerfRecord(TypedDict, total=False):
    name: str
    nodeid: str
    avg_ms: float
    thr_ms: float
    runs_ms: Sequence[float]


_perf_avgs: List[PerfRecord] = []  # collected performance averages


def pytest_runtest_logstart(
    nodeid: str, location: tuple[str, int, str]
) -> None:  # type: ignore[override]
    # nodeid 開始時刻記録 (setup も含む全体が知りたい場合はここ)
    _start_times[nodeid] = time.perf_counter()


def pytest_configure(config: pytest.Config) -> None:  # type: ignore[override]
    global _case_time_enabled
    global _perf_avg_enabled
    if config.getoption("case_time"):
        _case_time_enabled = True
        config.addinivalue_line(
            "markers", "case_time: per test timing enabled"
        )
    if config.getoption("perf_avg"):
        _perf_avg_enabled = True
        config.addinivalue_line(
            "markers", "perf_avg: performance average collection enabled"
        )


@pytest.fixture
def perf_recorder() -> Callable[[PerfRecord], None]:
    """Test から平均結果を記録するためのコールバック。

    使用例:
        perf_recorder({
            "name": case.name,
            "nodeid": request.node.nodeid,
            "avg_ms": avg * 1000,
            "thr_ms": thr * 1000,
            "runs_ms": [t * 1000 for t in times],
        })
    """

    def _rec(data: PerfRecord) -> None:
        if _perf_avg_enabled:
            _perf_avgs.append(data)

    return _rec


def pytest_runtest_logreport(report: pytest.TestReport) -> None:  # type: ignore[override]
    if not _case_time_enabled:
        return

    # call フェーズ終了時に表示 (失敗/成功問わず)
    if report.when == "call":
        # 優先: report.duration (pytest が測った call フェーズ時間)
        duration = report.duration
        # もし nodeid 開始を記録しており、setup 含む総時間を表示したいなら以下を利用
        total_duration: Optional[float] = None
        if report.nodeid in _start_times:
            total_duration = time.perf_counter() - _start_times[report.nodeid]

        # 色付け: 成功=緑, 失敗=赤, スキップ=黄 (ただし call で skipped は稀)
        outcome = report.outcome
        if outcome == "passed":
            color = "32"  # green
        elif outcome == "failed":
            color = "31"  # red
        else:
            color = "33"  # yellow

        total_part = (
            f" (total {total_duration:.3f}s incl. setup/teardown)"
            if total_duration is not None
            else ""
        )
        print(
            f"\x1b[{color}m[CASE-TIME] {report.nodeid}: call {duration:.3f}s{total_part}\x1b[0m"
        )


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:  # type: ignore[override]
    # 後始末 - メモリ再利用というほどではないが明示クリア
    _start_times.clear()
    if _perf_avg_enabled and _perf_avgs:
        # ソート (遅い順)
        ordered = sorted(
            _perf_avgs, key=lambda d: d.get("avg_ms", 0.0), reverse=True
        )
        print("\n===== PERF AVG (ms) =====")
        for rec in ordered:
            name = rec.get("name", "<unknown>")
            avg_ms = rec.get("avg_ms", 0.0)
            thr_ms = rec.get("thr_ms", 0.0)
            print(f"[PERF-AVG] {name}: avg={avg_ms:.3f}ms thr={thr_ms:.3f}ms")
        print("========================\n")
