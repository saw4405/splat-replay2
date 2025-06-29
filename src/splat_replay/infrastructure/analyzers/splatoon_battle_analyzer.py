"""スプラトゥーン対戦モード用フレームアナライザー。"""

from __future__ import annotations

from typing import Tuple, Dict

import numpy as np

from splat_replay.infrastructure.analyzers.common.image_utils import (
    MatcherRegistry,
    rotate_image
)
from splat_replay.shared.config import ImageMatchingSettings
from .plugin import AnalyzerPlugin
from .common.ocr import recognize_text
from splat_replay.domain.models import Match, RateBase, Udemae, XP, Rule, Stage
from splat_replay.shared.logger import get_logger


class BattleFrameAnalyzer(AnalyzerPlugin):
    """バトル向けフレーム解析ロジック。"""

    def __init__(self, settings: ImageMatchingSettings) -> None:
        self.registry = MatcherRegistry(settings)
        self._logger = get_logger()

    def extract_match_select(self, frame: np.ndarray) -> Match | None:
        match = self.registry.match_first_group("battle_select", frame)
        return Match(match) if match else None

    def extract_rate(self, frame: np.ndarray, match: Match) -> RateBase | None:
        """レートを取得する。"""
        if match.is_anarchy():
            udemae = self.registry.match_first_group(
                "battle_rate_udemae", frame)
            return Udemae(udemae) if udemae else None

        if match is Match.X:
            return self.extract_xp(frame)

        return None

    def extract_xp(self, frame: np.ndarray) -> XP | None:
        """XPを取得する。"""
        xp_image = frame[190:240, 1730:1880]
        xp_image = rotate_image(xp_image, -4)
        xp_str = recognize_text(xp_image)
        if xp_str is None:
            self._logger.warning(f"XパワーのOCRに失敗しました")
            return None
        xp_str = xp_str.strip()

        try:
            xp = float(xp_str)
        except ValueError:
            self._logger.warning(f"Xパワーが数値ではありません: {xp_str}")
            return None

        if xp < 500 or xp > 5500:
            self._logger.warning(f"Xパワーが異常です: {xp}")
            return None

        return XP(xp)

    def detect_matching_start(self, frame: np.ndarray) -> bool:
        return False

    def detect_schedule_change(self, frame: np.ndarray) -> bool:
        return False

    def detect_battle_start(self, frame: np.ndarray) -> bool:
        return self.registry.match("battle_start", frame)

    def detect_battle_abort(self, frame: np.ndarray) -> bool:
        return self.registry.match("battle_abort", frame)

    def detect_battle_finish(self, frame: np.ndarray) -> bool:
        return self.registry.match("battle_finish", frame)

    def detect_battle_finish_end(self, frame: np.ndarray) -> bool:
        return self.detect_battle_judgement(frame)

    def detect_battle_judgement(self, frame: np.ndarray) -> bool:
        return self.registry.match("battle_judgement_latter_half", frame)

    def extract_battle_judgement(self, frame: np.ndarray) -> str | None:
        """勝敗画面から勝敗を取得する。"""
        return self.registry.match_first_group("battle_judgements", frame)

    def detect_loading(self, frame: np.ndarray) -> bool:
        return self.registry.match("loading", frame)

    def detect_loading_end(self, frame: np.ndarray) -> bool:
        return self.registry.match("loading_end", frame)

    def detect_battle_result(self, frame: np.ndarray) -> bool:
        return self.registry.match("battle_result", frame)

    def extract_battle_match(self, frame: np.ndarray) -> Match | None:
        """バトルマッチの種類を取得する。"""
        return Match(self.registry.match_first_group("battle_matches", frame))

    def extract_battle_rule(self, frame: np.ndarray) -> Rule | None:
        """バトルルールを取得する。"""
        return Rule(self.registry.match_first_group("battle_rules", frame))

    def extract_battle_stage(self, frame: np.ndarray) -> Stage | None:
        """バトルステージを取得する。"""
        return Stage(self.registry.match_first_group("battle_stages", frame))

    def extract_battle_kill_record(
        self, frame: np.ndarray, match: Match
    ) -> Tuple[int, int, int] | None:
        """キルレコードを取得する。"""
        if match == Match.TRICOLOR:
            record_positions: Dict[str, Dict[str, int]] = {
                "kill": {"x1": 1556, "y1": 293, "x2": 1585, "y2": 316},
                "death": {"x1": 1616, "y1": 293, "x2": 1644, "y2": 316},
                "special": {"x1": 1674, "y1": 293, "x2": 1703, "y2": 316}
            }
        else:
            record_positions: Dict[str, Dict[str, int]] = {
                "kill": {"x1": 1519, "y1": 293, "x2": 1548, "y2": 316},
                "death": {"x1": 1597, "y1": 293, "x2": 1626, "y2": 316},
                "special": {"x1": 1674, "y1": 293, "x2": 1703, "y2": 316}
            }

        records: Dict[str, int] = {}
        for name, position in record_positions.items():
            count_image = frame[position["y1"]:position["y2"],
                                position["x1"]:position["x2"]]

            # 文字認識の精度向上のため、拡大・余白・白文字・細字化を行う
            import cv2
            count_image = cv2.resize(count_image, (0, 0), fx=3.5, fy=3.5)
            count_image = cv2.copyMakeBorder(
                count_image, 50, 50, 50, 50, cv2.BORDER_CONSTANT, value=(0, 0, 0))
            count_image = cv2.cvtColor(count_image, cv2.COLOR_BGR2GRAY)
            count_image = cv2.threshold(
                count_image, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
            count_image = cv2.erode(
                count_image, np.ones((2, 2), np.uint8), iterations=5)
            count_image = cv2.bitwise_not(count_image)

            count_str = recognize_text(
                count_image, "SINGLE_LINE", "0123456789")
            if count_str is None:
                self._logger.warning(
                    f"{name}数のOCRに失敗しました")
                return None

            count_str = count_str.strip()
            try:
                count = int(count_str)
                records[name] = count
            except ValueError:
                self._logger.warning(f"{name}数が数値ではありません: {count_str}")

        if len(records) != 3:
            return None
        return records["kill"], records["death"], records["special"]
