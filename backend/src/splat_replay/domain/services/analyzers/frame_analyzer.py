"""ゲーム画面を解析するサービス。"""

from __future__ import annotations

from typing import Optional

from splat_replay.domain.models import (
    Frame,
    GameMode,
    Judgement,
    Match,
    RateBase,
    Result,
)

from .battle_analyzer import BattleFrameAnalyzer
from splat_replay.domain.ports import ImageMatcherPort
from .salmon_analyzer import SalmonFrameAnalyzer


class FrameAnalyzer:
    """OpenCV を用いた画面解析処理を提供する。"""

    def __init__(
        self,
        battle_plugin: BattleFrameAnalyzer,
        salmon_plugin: SalmonFrameAnalyzer,
        matcher: ImageMatcherPort,
    ) -> None:
        """2 種類のプラグインと設定を受け取って初期化する。"""
        self.plugins = {
            GameMode.BATTLE: battle_plugin,
            GameMode.SALMON: salmon_plugin,
        }
        self.matcher = matcher

    async def detect_power_off(self, frame: Frame) -> bool:
        """Switch の電源 OFF を検出する。"""
        return await self.matcher.match("power_off", frame)

    async def detect_match_select(self, frame: Frame) -> bool:
        """マッチ選択画面かを判定する。"""
        return await self.matcher.match("match_select", frame)

    async def extract_game_mode(self, frame: Frame) -> Optional[GameMode]:
        """ゲームモードを抽出する。"""
        for mode in GameMode:
            match = await self.extract_match_select(frame, mode)
            if match:
                return mode
        return None

    async def extract_match_select(
        self, frame: Frame, mode: GameMode
    ) -> Optional[Match]:
        plugin = self.plugins.get(mode)
        if plugin is None:
            return None
        return await plugin.extract_match_select(frame)

    async def extract_rate(
        self, frame: Frame, mode: GameMode
    ) -> Optional[RateBase]:
        plugin = self.plugins.get(mode)
        if plugin is None:
            return None
        match = await plugin.extract_match_select(frame)
        if match is None:
            return None
        return await plugin.extract_rate(frame, match)

    async def detect_matching_start(self, frame: Frame) -> bool:
        """マッチング開始画面を検出する。"""
        return await self.matcher.match("matching_start", frame)

    async def detect_schedule_change(self, frame: Frame) -> bool:
        return await self.matcher.match("schedule_change", frame)

    async def detect_session_start(self, frame: Frame, mode: GameMode) -> bool:
        plugin = self.plugins.get(mode)
        if plugin is None:
            return False
        return await plugin.detect_session_start(frame)

    async def detect_session_abort(self, frame: Frame, mode: GameMode) -> bool:
        plugin = self.plugins.get(mode)
        if plugin is None:
            return False
        return await plugin.detect_session_abort(frame)

    async def detect_communication_error(
        self, frame: Frame, mode: GameMode
    ) -> bool:
        plugin = self.plugins.get(mode)
        if plugin is None:
            return False
        return await plugin.detect_communication_error(frame)

    async def detect_session_finish(
        self, frame: Frame, mode: GameMode
    ) -> bool:
        plugin = self.plugins.get(mode)
        if plugin is None:
            return False
        return await plugin.detect_session_finish(frame)

    async def detect_session_finish_end(
        self, frame: Frame, mode: GameMode
    ) -> bool:
        plugin = self.plugins.get(mode)
        if plugin is None:
            return False
        return await plugin.detect_session_finish_end(frame)

    async def detect_session_judgement(
        self, frame: Frame, mode: GameMode
    ) -> bool:
        plugin = self.plugins.get(mode)
        if plugin is None:
            return False
        return await plugin.detect_session_judgement(frame)

    async def extract_session_judgement(
        self, frame: Frame, mode: GameMode
    ) -> Optional[Judgement]:
        """バトルの結果を抽出する。"""
        plugin = self.plugins.get(mode)
        if plugin is None:
            return None
        return await plugin.extract_session_judgement(frame)

    async def detect_loading(self, frame: Frame) -> bool:
        """ローディング画面かどうか判定する。"""
        return await self.matcher.match("loading", frame)

    async def detect_loading_end(self, frame: Frame) -> bool:
        """ローディング終了を検出する。"""
        return not await self.detect_loading(frame)

    async def detect_session_result(
        self, frame: Frame, mode: GameMode
    ) -> bool:
        """結果画面を検出する。"""
        plugin = self.plugins.get(mode)
        if plugin is None:
            return False
        return await plugin.detect_session_result(frame)

    async def extract_session_result(
        self, frame: Frame, mode: GameMode
    ) -> Optional[Result]:
        """バトルの結果を抽出する。"""
        plugin = self.plugins.get(mode)
        if plugin is None:
            return None

        return await plugin.extract_session_result(frame)
