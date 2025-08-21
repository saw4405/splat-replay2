"""スプラトゥーン対戦モード用フレームアナライザー。"""

from __future__ import annotations

from typing import Dict, Optional, Tuple

from structlog.stdlib import BoundLogger

from splat_replay.domain.models import (
    XP,
    BattleResult,
    Frame,
    Match,
    RateBase,
    Rule,
    Stage,
    Udemae,
)

from .analyzer_plugin import AnalyzerPlugin
from .image_editor import ImageEditorFactory
from .image_matcher import ImageMatcherPort
from .ocr import OCRPort


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

    async def extract_match_select(self, frame: Frame) -> Optional[Match]:
        match = await self.matcher.matched_name("battle_select", frame)
        return Match(match) if match else None

    async def extract_rate(
        self, frame: Frame, match: Match
    ) -> Optional[RateBase]:
        """レートを取得する。"""
        if match.is_anarchy():
            udemae = await self.matcher.matched_name(
                "battle_rate_udemae", frame
            )
            return Udemae(udemae) if udemae else None

        if match is Match.X:
            return await self.extract_xp(frame)

        return None

    async def extract_xp(self, frame: Frame) -> Optional[XP]:
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

    async def detect_session_start(self, frame: Frame) -> bool:
        return await self.matcher.match("battle_start", frame)

    async def detect_session_abort(self, frame: Frame) -> bool:
        return await self.matcher.match("battle_abort", frame)

    async def detect_session_finish(self, frame: Frame) -> bool:
        return await self.matcher.match("battle_finish", frame)

    async def detect_session_finish_end(self, frame: Frame) -> bool:
        return await self.detect_session_judgement(frame)

    async def detect_session_judgement(self, frame: Frame) -> bool:
        return await self.matcher.match("battle_judgement_latter_half", frame)

    async def extract_session_judgement(self, frame: Frame) -> Optional[str]:
        """勝敗画面から勝敗を取得する。"""
        return await self.matcher.matched_name("battle_judgements", frame)

    async def detect_session_result(self, frame: Frame) -> bool:
        return await self.matcher.match("battle_result", frame)

    async def extract_session_result(
        self, frame: Frame
    ) -> Optional[BattleResult]:
        match = await self.extract_battle_match(frame)
        if match is None:
            self._logger.warning("バトルマッチが抽出できません")
            return None
        rule = await self.extract_battle_rule(frame)
        if rule is None:
            self._logger.warning("バトルルールが抽出できません")
            return None
        stage = await self.extract_battle_stage(frame)
        if stage is None:
            self._logger.warning("バトルステージが抽出できません")
            return None
        kill_record = await self.extract_battle_kill_record(frame, match)
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

    async def extract_battle_match(self, frame: Frame) -> Optional[Match]:
        """バトルマッチの種類を取得する。"""
        return Match(await self.matcher.matched_name("battle_matches", frame))

    async def extract_battle_rule(self, frame: Frame) -> Optional[Rule]:
        """バトルルールを取得する。"""
        return Rule(await self.matcher.matched_name("battle_rules", frame))

    async def extract_battle_stage(self, frame: Frame) -> Optional[Stage]:
        """バトルステージを取得する。"""
        return Stage(await self.matcher.matched_name("battle_stages", frame))

    async def extract_battle_kill_record(
        self, frame: Frame, match: Match
    ) -> Optional[Tuple[int, int, int]]:
        """キルレコードを取得する。"""
        record_positions: Dict[str, Dict[str, int]] = {
            "kill": {"x1": 1519, "y1": 293, "x2": 1548, "y2": 316},
            "death": {"x1": 1597, "y1": 293, "x2": 1626, "y2": 316},
            "special": {"x1": 1674, "y1": 293, "x2": 1703, "y2": 316},
        }

        kill_record = await self._extract_battle_kill_record(
            frame, record_positions
        )

        # トリカラの攻撃側のときはキルレ表示の位置が異なるため、再度抽出する
        if not kill_record and match == Match.TRICOLOR:
            record_positions: Dict[str, Dict[str, int]] = {
                "kill": {"x1": 1556, "y1": 293, "x2": 1585, "y2": 316},
                "death": {"x1": 1616, "y1": 293, "x2": 1644, "y2": 316},
                "special": {"x1": 1674, "y1": 293, "x2": 1703, "y2": 316},
            }
            kill_record = await self._extract_battle_kill_record(
                frame, record_positions
            )

        return kill_record

    async def _extract_battle_kill_record(
        self, frame: Frame, record_positions: Dict[str, Dict[str, int]]
    ) -> Optional[Tuple[int, int, int]]:
        records: Dict[str, int] = {}
        for name, position in record_positions.items():
            count_image = frame[
                position["y1"] : position["y2"],
                position["x1"] : position["x2"],
            ]

            count_image = (
                self.image_editor_factory(count_image)
                .resize(3, 3)
                .padding(50, 50, 50, 50, (0, 0, 0))
                .binarize()
                .erode((2, 2), 2)
                .invert()
                .image
            )

            count_str = await self.ocr.recognize_text(
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
