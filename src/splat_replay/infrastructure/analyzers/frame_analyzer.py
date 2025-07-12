"""ゲーム画面を解析するサービス。"""

from __future__ import annotations

import numpy as np

from splat_replay.infrastructure.analyzers.common.image_utils import (
    MatcherRegistry,
)

from splat_replay.application.interfaces import FrameAnalyzerPort
from splat_replay.shared.config import ImageMatchingSettings
from splat_replay.domain.models import (
    GameMode,
    Match,
    RateBase,
    Result,
    BattleResult,
)
from splat_replay.infrastructure.analyzers.splatoon_battle_analyzer import (
    BattleFrameAnalyzer,
)
from splat_replay.infrastructure.analyzers.splatoon_salmon_analyzer import (
    SalmonFrameAnalyzer,
)
from splat_replay.shared.logger import get_logger

logger = get_logger()


class FrameAnalyzer(FrameAnalyzerPort):
    """OpenCV を用いた画面解析処理を提供する。"""

    def __init__(
        self,
        battle_plugin: BattleFrameAnalyzer,
        salmon_plugin: SalmonFrameAnalyzer,
        settings: ImageMatchingSettings,
    ) -> None:
        """2 種類のプラグインと設定を受け取って初期化する。"""
        self.plugins = {
            GameMode.BATTLE: battle_plugin,
            GameMode.SALMON: salmon_plugin,
        }
        self.mode = GameMode.UNKNOWN
        self.match: Match | None = None
        self.registry = MatcherRegistry(settings)

    def set_mode(self, mode: GameMode) -> None:
        """解析モードを設定する。"""
        if mode not in self.plugins:
            raise ValueError(f"Unsupported game mode: {mode}")
        self.mode = mode

    def reset(self) -> None:
        """モードを未確定状態へ戻す。"""
        self.match = None
        self.mode = GameMode.UNKNOWN

    def detect_power_off(self, frame: np.ndarray) -> bool:
        """Switch の電源 OFF を検出する。"""
        return self.registry.match("power_off", frame)

    def detect_match_select(self, frame: np.ndarray) -> bool:
        """マッチ選択画面かを判定しモードを設定する。"""
        detected = self.registry.match("match_select", frame)
        for mode in GameMode:
            plugin = self.plugins.get(mode)
            if plugin is None:
                continue
            match = plugin.extract_match_select(frame)
            if match:
                self.match = match
                self.mode = mode
                return True

        return detected

    def extract_rate(self, frame: np.ndarray) -> RateBase | None:
        plugin = self.plugins.get(self.mode)
        if plugin is None:
            return None
        if self.match is None:
            logger.warning("マッチが未設定のためレートを抽出できません")
            return None
        return plugin.extract_rate(frame, self.match)

    def detect_matching_start(self, frame: np.ndarray) -> bool:
        """マッチング開始画面を検出する。"""
        return self.registry.match("matching_start", frame)

    def detect_schedule_change(self, frame: np.ndarray) -> bool:
        return self.registry.match("schedule_change", frame)

    def detect_battle_start(self, frame: np.ndarray) -> bool:
        plugin = self.plugins.get(self.mode)
        if plugin is None:
            return False
        return plugin.detect_battle_start(frame)

    def detect_battle_abort(self, frame: np.ndarray) -> bool:
        plugin = self.plugins.get(self.mode)
        if plugin is None:
            return False
        return plugin.detect_battle_abort(frame)

    def detect_battle_finish(self, frame: np.ndarray) -> bool:
        plugin = self.plugins.get(self.mode)
        if plugin is None:
            return False
        return plugin.detect_battle_finish(frame)

    def detect_battle_finish_end(self, frame: np.ndarray) -> bool:
        plugin = self.plugins.get(self.mode)
        if plugin is None:
            return False
        return plugin.detect_battle_finish_end(frame)

    def detect_battle_judgement(self, frame: np.ndarray) -> bool:
        plugin = self.plugins.get(self.mode)
        if plugin is None:
            return False
        return plugin.detect_battle_judgement(frame)

    def extract_battle_judgement(self, frame: np.ndarray) -> str | None:
        """バトルの結果を抽出する。"""
        plugin = self.plugins.get(self.mode)
        if plugin is None:
            return None
        return plugin.extract_battle_judgement(frame)

    def detect_loading(self, frame: np.ndarray) -> bool:
        """ローディング画面かどうか判定する。"""
        return self.registry.match("loading", frame)

    def detect_loading_end(self, frame: np.ndarray) -> bool:
        """ローディング終了を検出する。"""
        return not self.detect_loading(frame)

    def detect_battle_result(self, frame: np.ndarray) -> bool:
        """結果画面を検出する。"""
        plugin = self.plugins.get(self.mode)
        if plugin is None:
            return False
        return plugin.detect_battle_result(frame)

    def extract_battle_result(self, frame: np.ndarray) -> Result | None:
        """バトルの結果を抽出する。"""
        plugin = self.plugins.get(self.mode)
        if plugin is None:
            return None

        if isinstance(plugin, BattleFrameAnalyzer):
            match = plugin.extract_battle_match(frame)
            if match is None:
                logger.warning("バトルマッチが抽出できません")
                return None
            rule = plugin.extract_battle_rule(frame)
            if rule is None:
                logger.warning("バトルルールが抽出できません")
                return None
            stage = plugin.extract_battle_stage(frame)
            if stage is None:
                logger.warning("バトルステージが抽出できません")
                return None
            kill_record = plugin.extract_battle_kill_record(frame, match)
            if kill_record is None:
                logger.warning("キルレコードが抽出できません")
                return None

            return BattleResult(
                match=match,
                rule=rule,
                stage=stage,
                kill=kill_record[0],
                death=kill_record[1],
                special=kill_record[2],
            )

        elif isinstance(plugin, SalmonFrameAnalyzer):
            raise NotImplementedError("サーモンランの結果抽出は未実装です")

        return None
