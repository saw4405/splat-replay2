"""解析プラグイン共通インターフェース。"""

from __future__ import annotations

from typing import Optional, Protocol

from splat_replay.domain.models import Frame, Match, RateBase, Result


class AnalyzerPlugin(Protocol):
    """ゲーム画面解析プラグインのプロトコル。"""

    async def extract_match_select(self, frame: Frame) -> Optional[Match]: ...

    async def extract_rate(
        self, frame: Frame, match: Match
    ) -> Optional[RateBase]: ...

    async def detect_session_start(self, frame: Frame) -> bool: ...

    async def detect_session_abort(self, frame: Frame) -> bool: ...

    async def detect_session_finish(self, frame: Frame) -> bool: ...

    async def detect_session_finish_end(self, frame: Frame) -> bool: ...

    async def detect_session_judgement(self, frame: Frame) -> bool: ...

    async def extract_session_judgement(
        self, frame: Frame
    ) -> Optional[str]: ...

    async def detect_session_result(self, frame: Frame) -> bool: ...

    async def extract_session_result(
        self, frame: Frame
    ) -> Optional[Result]: ...
