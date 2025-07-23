"""スプラトゥーン対戦モード用フレームアナライザー。"""

from __future__ import annotations

from typing import Tuple, Dict, Optional

from structlog.stdlib import BoundLogger
from splat_replay.domain.models import (
    Frame,
    Match,
    RateBase,
    Udemae,
    XP,
    Rule,
    Stage,
    BattleResult,
)
from .image_matcher import ImageMatcherPort
from .ocr import OCRPort
from .analyzer_plugin import AnalyzerPlugin
from .image_editor import ImageEditorFactory


class BattleFrameAnalyzer(AnalyzerPlugin):
    """バトル向けフレーム解析ロジック。"""

    def __init__(
        self,
        matcher: ImageMatcherPort,
        ocr: OCRPort,
        image_editor_factory: ImageEditorFactory,
        logger: BoundLogger,
    ) -> None:
        self.matcher = matcher
        self._logger = logger
        self.ocr = ocr
        self.image_editor_factory = image_editor_factory

    def extract_match_select(self, frame: Frame) -> Optional[Match]:
        match = self.matcher.matched_name("battle_select", frame)
        if match:
            return Match(match)
        if self.matcher.match("match_select_splatfest", frame):
            return Match.SPLATFEST
        return None

    def extract_rate(self, frame: Frame, match: Match) -> Optional[RateBase]:
        """レートを取得する。"""
        if match.is_anarchy():
            udemae = self.matcher.matched_name("battle_rate_udemae", frame)
            return Udemae(udemae) if udemae else None

        if match is Match.X:
            return self.extract_xp(frame)

        return None

    def extract_xp(self, frame: Frame) -> Optional[XP]:
        """XPを取得する。"""
        xp_image = frame[190:240, 1730:1880]
        xp_image = self.image_editor_factory(xp_image).rotate(-4).image
        xp_str = self.ocr.recognize_text(xp_image)
        if xp_str is None:
            self._logger.warning("XパワーのOCRに失敗しました")
            return None
        xp_str = xp_str.strip()

        try:
            xp = float(xp_str)
        except ValueError:
            self._logger.warning(f"Xパワーが数値ではありません: {xp_str}")
            return None

        return XP(xp)

    def detect_session_start(self, frame: Frame) -> bool:
        return self.matcher.match("battle_start", frame)

    def detect_session_abort(self, frame: Frame) -> bool:
        return self.matcher.match("battle_abort", frame)

    def detect_session_finish(self, frame: Frame) -> bool:
        return self.matcher.match("battle_finish", frame)

    def detect_session_finish_end(self, frame: Frame) -> bool:
        return self.detect_session_judgement(frame)

    def detect_session_judgement(self, frame: Frame) -> bool:
        return self.matcher.match("battle_judgement_latter_half", frame)

    def extract_session_judgement(self, frame: Frame) -> Optional[str]:
        """勝敗画面から勝敗を取得する。"""
        return self.matcher.matched_name("battle_judgements", frame)

    def detect_session_result(self, frame: Frame) -> bool:
        return self.matcher.match("battle_result", frame)

    def extract_session_result(self, frame: Frame) -> Optional[BattleResult]:
        match = self.extract_battle_match(frame)
        if match is None:
            self._logger.warning("バトルマッチが抽出できません")
            return None
        rule = self.extract_battle_rule(frame)
        if rule is None:
            self._logger.warning("バトルルールが抽出できません")
            return None
        stage = self.extract_battle_stage(frame)
        if stage is None:
            self._logger.warning("バトルステージが抽出できません")
            return None
        kill_record = self.extract_battle_kill_record(frame, match)
        if kill_record is None:
            self._logger.warning("キルレコードが抽出できません")
            return None

        return BattleResult(
            match=match,
            rule=rule,
            stage=stage,
            kill=kill_record[0],
            death=kill_record[1],
            special=kill_record[2],
        )

    def extract_battle_match(self, frame: Frame) -> Optional[Match]:
        """バトルマッチの種類を取得する。"""
        return Match(self.matcher.matched_name("battle_matches", frame))

    def extract_battle_rule(self, frame: Frame) -> Optional[Rule]:
        """バトルルールを取得する。"""
        return Rule(self.matcher.matched_name("battle_rules", frame))

    def extract_battle_stage(self, frame: Frame) -> Optional[Stage]:
        """バトルステージを取得する。"""
        return Stage(self.matcher.matched_name("battle_stages", frame))

    def extract_battle_kill_record(
        self, frame: Frame, match: Match
    ) -> Optional[Tuple[int, int, int]]:
        """キルレコードを取得する。"""
        if match == Match.TRICOLOR:
            record_positions: Dict[str, Dict[str, int]] = {
                "kill": {"x1": 1556, "y1": 293, "x2": 1585, "y2": 316},
                "death": {"x1": 1616, "y1": 293, "x2": 1644, "y2": 316},
                "special": {"x1": 1674, "y1": 293, "x2": 1703, "y2": 316},
            }
        else:
            record_positions: Dict[str, Dict[str, int]] = {
                "kill": {"x1": 1519, "y1": 293, "x2": 1548, "y2": 316},
                "death": {"x1": 1597, "y1": 293, "x2": 1626, "y2": 316},
                "special": {"x1": 1674, "y1": 293, "x2": 1703, "y2": 316},
            }

        records: Dict[str, int] = {}
        for name, position in record_positions.items():
            count_image = frame[
                position["y1"] : position["y2"],
                position["x1"] : position["x2"],
            ]

            count_image = (
                self.image_editor_factory(count_image)
                .resize(3.5, 3.5)
                .padding(50, 50, 50, 50, (0, 0, 0))
                .binarize()
                .erode((2, 2), 5)
                .invert()
                .image
            )

            count_str = self.ocr.recognize_text(
                count_image, ps_mode="SINGLE_LINE", whitelist="0123456789"
            )
            if count_str is None:
                self._logger.warning(f"{name}数のOCRに失敗しました")
                return None

            count_str = count_str.strip()
            try:
                count = int(count_str)
                records[name] = count
            except ValueError:
                self._logger.warning(
                    f"{name}数が数値ではありません: {count_str}"
                )

        if len(records) != 3:
            return None
        return records["kill"], records["death"], records["special"]
