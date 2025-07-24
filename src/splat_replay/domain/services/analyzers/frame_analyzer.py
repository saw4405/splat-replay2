"""ゲーム画面を解析するサービス。"""

from __future__ import annotations

from typing import Optional

from splat_replay.domain.models import (
    Frame,
    GameMode,
    Match,
    RateBase,
    Result,
)
from .image_matcher import ImageMatcherPort
from .battle_analyzer import BattleFrameAnalyzer
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

    def detect_power_off(self, frame: Frame) -> bool:
        """Switch の電源 OFF を検出する。"""
        return self.matcher.match("power_off", frame)

    def detect_match_select(self, frame: Frame) -> bool:
        """マッチ選択画面かを判定する。"""
        return self.matcher.match("match_select", frame)

    def extract_game_mode(self, frame: Frame) -> Optional[GameMode]:
        """ゲームモードを抽出する。"""
        for mode in GameMode:
            match = self.extract_match_select(frame, mode)
            if match:
                return mode
        return None

    def extract_match_select(self, frame: Frame, mode: GameMode) -> Optional[Match]:
        plugin = self.plugins.get(mode)
        if plugin is None:
            return None
        return plugin.extract_match_select(frame)

    def extract_rate(self, frame: Frame, mode: GameMode) -> Optional[RateBase]:
        plugin = self.plugins.get(mode)
        if plugin is None:
            return None
        match = plugin.extract_match_select(frame)
        if match is None:
            return None
        return plugin.extract_rate(frame, match)

    def detect_matching_start(self, frame: Frame) -> bool:
        """マッチング開始画面を検出する。"""
        return self.matcher.match("matching_start", frame)

    def detect_schedule_change(self, frame: Frame) -> bool:
        return self.matcher.match("schedule_change", frame)

    def detect_session_start(self, frame: Frame, mode: GameMode) -> bool:
        plugin = self.plugins.get(mode)
        if plugin is None:
            return False
        return plugin.detect_session_start(frame)

    def detect_session_abort(self, frame: Frame, mode: GameMode) -> bool:
        plugin = self.plugins.get(mode)
        if plugin is None:
            return False
        return plugin.detect_session_abort(frame)

    def detect_session_finish(self, frame: Frame, mode: GameMode) -> bool:
        plugin = self.plugins.get(mode)
        if plugin is None:
            return False
        return plugin.detect_session_finish(frame)

    def detect_session_finish_end(self, frame: Frame, mode: GameMode) -> bool:
        plugin = self.plugins.get(mode)
        if plugin is None:
            return False
        return plugin.detect_session_finish_end(frame)

    def detect_session_judgement(self, frame: Frame, mode: GameMode) -> bool:
        plugin = self.plugins.get(mode)
        if plugin is None:
            return False
        return plugin.detect_session_judgement(frame)

    def extract_session_judgement(
        self, frame: Frame, mode: GameMode
    ) -> Optional[str]:
        """バトルの結果を抽出する。"""
        plugin = self.plugins.get(mode)
        if plugin is None:
            return None
        return plugin.extract_session_judgement(frame)

    def detect_loading(self, frame: Frame) -> bool:
        """ローディング画面かどうか判定する。"""
        return self.matcher.match("loading", frame)

    def detect_loading_end(self, frame: Frame) -> bool:
        """ローディング終了を検出する。"""
        return not self.detect_loading(frame)

    def detect_session_result(self, frame: Frame, mode: GameMode) -> bool:
        """結果画面を検出する。"""
        plugin = self.plugins.get(mode)
        if plugin is None:
            return False
        return plugin.detect_session_result(frame)

    def extract_session_result(
        self, frame: Frame, mode: GameMode
    ) -> Optional[Result]:
        """バトルの結果を抽出する。"""
        plugin = self.plugins.get(mode)
        if plugin is None:
            return None

        return plugin.extract_session_result(frame)
