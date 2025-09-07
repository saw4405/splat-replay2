"""サーモンラン用フレームアナライザー。"""

from __future__ import annotations

from typing import Optional

from splat_replay.domain.models import (
    Frame,
    Judgement,
    Match,
    RateBase,
    SalmonResult,
)

from .analyzer_plugin import AnalyzerPlugin
from .image_matcher import ImageMatcherPort


class SalmonFrameAnalyzer(AnalyzerPlugin):
    """サーモンラン向けのフレーム解析ロジック。"""

    def __init__(self, matcher: ImageMatcherPort) -> None:
        self.matcher = matcher

    async def extract_match_select(self, frame: Frame) -> Optional[Match]:
        return None

    async def extract_rate(
        self, frame: Frame, match: Match
    ) -> Optional[RateBase]:
        raise NotImplementedError()

    async def detect_session_start(self, frame: Frame) -> bool:
        raise NotImplementedError()

    async def detect_session_abort(self, frame: Frame) -> bool:
        raise NotImplementedError()

    async def detect_communication_error(self, frame: Frame) -> bool:
        raise NotImplementedError()

    async def detect_session_finish(self, frame: Frame) -> bool:
        raise NotImplementedError()

    async def detect_session_finish_end(self, frame: Frame) -> bool:
        raise NotImplementedError()

    async def detect_session_judgement(self, frame: Frame) -> bool:
        raise NotImplementedError()

    async def extract_session_judgement(
        self, frame: Frame
    ) -> Optional[Judgement]:
        raise NotImplementedError()

    async def detect_session_result(self, frame: Frame) -> bool:
        raise NotImplementedError()

    async def extract_session_result(
        self, frame: Frame
    ) -> Optional[SalmonResult]:
        raise NotImplementedError()
