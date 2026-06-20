"""スプラトゥーン対戦モード用フレームアナライザー。"""

from __future__ import annotations

import asyncio
from typing import Optional, Tuple

from splat_replay.domain.models import (
    XP,
    BattleResult,
    Frame,
    Judgement,
    Match,
    RateBase,
    Rule,
    Stage,
    Udemae,
    as_frame,
)
from splat_replay.domain.ports import (
    BattleMedalRecognizerPort,
    ImageEditorFactory,
    ImageEditorPort,
    ImageMatcherPort,
    OCRPort,
)

from .analyzer_plugin import AnalyzerPlugin
from .kill_record_extractor import KillRecordExtractor
from .xp_detection import (
    XPExtractionDiagnostics,
    XP_BINARIZE_THRESHOLD,
    XP_FOREGROUND_THRESHOLD,
    XP_MIN_COMPONENT_AREA,
    parse_xp_ocr_text,
    validate_xp_processed_component_count,
)


class _NullBattleMedalRecognizer:
    async def count_medals(self, frame: Frame) -> Tuple[int, int]:
        _ = frame
        return 0, 0


class BattleFrameAnalyzer(AnalyzerPlugin):
    """バトル向けフレーム解析ロジック。"""

    def __init__(
        self,
        matcher: ImageMatcherPort,
        ocr: OCRPort,
        image_editor_factory: ImageEditorFactory,
        medal_recognizer: BattleMedalRecognizerPort = _NullBattleMedalRecognizer(),
    ) -> None:
        self.matcher = matcher
        self.ocr = ocr
        self.image_editor_factory = image_editor_factory
        self.medal_recognizer = medal_recognizer
        self._kill_record_extractor = KillRecordExtractor(
            ocr, image_editor_factory
        )

    # ---------------------------------------------------------------
    # 内部ユーティリティ
    # ---------------------------------------------------------------
    async def _ensure_ocr_warm(self) -> None:
        # OCR のウォームアップは重いので、ここでは行わない
        return None

    async def extract_match_select(self, frame: Frame) -> Optional[Match]:
        match = await self.matcher.matched_name("battle_select", frame)
        return Match(match) if match else None

    async def extract_rate(
        self, frame: Frame, match: Match
    ) -> Optional[RateBase]:
        """レートを取得する。"""
        try:
            if match.is_anarchy():
                udemae = await self.matcher.matched_name(
                    "battle_rate_udemae", frame
                )
                return Udemae(Udemae.validate_rank(udemae)) if udemae else None

            if match is Match.X:
                return await self.extract_xp(frame)

            if match is Match.CHALLENGE:
                return await self.extract_event_power(frame)
        except Exception:
            return None
        return None

    async def extract_xp(self, frame: Frame) -> Optional[XP]:
        """XPを取得する。"""
        xp_image = as_frame(frame[190:240, 1730:1880].copy())
        diagnostics = await self._extract_xp_from_roi(xp_image)
        return diagnostics.xp

    async def extract_event_power(self, frame: Frame) -> Optional[XP]:
        """最高イベントパワーを取得する。"""
        if not await self.matcher.match("battle_rate_event_power_best", frame):
            return None
        # 指定ROIの下端にOCRノイズが入るため、OCR入力はXPと同じ高さにそろえる。
        event_power_ocr_image = as_frame(frame[190:240, 1710:1860].copy())
        diagnostics = await self._extract_xp_from_roi(event_power_ocr_image)
        return diagnostics.xp

    def _prepare_xp_editor(self, xp_image: Frame) -> ImageEditorPort:
        return (
            self.image_editor_factory(xp_image)
            .rotate(-4)
            .resize(2, 2)
            .binarize(threshold=XP_BINARIZE_THRESHOLD)
            .invert()
        )

    async def _extract_xp_from_roi(
        self, xp_image: Frame
    ) -> XPExtractionDiagnostics:
        xp_editor = self._prepare_xp_editor(xp_image)
        xp_proc = xp_editor.image
        xp_str = await self.ocr.recognize_text(
            xp_proc, ps_mode="SINGLE_LINE", whitelist="0123456789."
        )
        component_count = xp_editor.count_connected_components(
            foreground_threshold=XP_FOREGROUND_THRESHOLD,
            min_area=XP_MIN_COMPONENT_AREA,
        )
        if xp_str is None:
            return XPExtractionDiagnostics(
                xp_roi=xp_image,
                xp_processed=xp_proc,
                ocr_text=None,
                parsed_xp=None,
                xp=None,
                validation_error=None,
                xp_processed_connected_component_count=component_count,
            )
        parsed_xp, validation_error = parse_xp_ocr_text(xp_str)
        if validation_error is not None or parsed_xp is None:
            return XPExtractionDiagnostics(
                xp_roi=xp_image,
                xp_processed=xp_proc,
                ocr_text=xp_str,
                parsed_xp=None,
                xp=None,
                validation_error=validation_error,
                xp_processed_connected_component_count=component_count,
            )
        validation_error = validate_xp_processed_component_count(
            component_count
        )
        if validation_error is not None:
            return XPExtractionDiagnostics(
                xp_roi=xp_image,
                xp_processed=xp_proc,
                ocr_text=xp_str,
                parsed_xp=parsed_xp,
                xp=None,
                validation_error=validation_error,
                xp_processed_connected_component_count=component_count,
            )
        try:
            xp = XP(parsed_xp)
        except Exception as exc:
            return XPExtractionDiagnostics(
                xp_roi=xp_image,
                xp_processed=xp_proc,
                ocr_text=xp_str,
                parsed_xp=parsed_xp,
                xp=None,
                validation_error=str(exc),
                xp_processed_connected_component_count=component_count,
            )
        return XPExtractionDiagnostics(
            xp_roi=xp_image,
            xp_processed=xp_proc,
            ocr_text=xp_str,
            parsed_xp=parsed_xp,
            xp=xp,
            validation_error=None,
            xp_processed_connected_component_count=component_count,
        )

    async def extract_xp_diagnostics(
        self, frame: Frame
    ) -> XPExtractionDiagnostics:
        """XP OCR の診断情報を含めて抽出する。"""
        xp_image = as_frame(frame[190:240, 1730:1880].copy())
        xp_editor = (
            self.image_editor_factory(xp_image)
            .rotate(-4)
            .resize(2, 2)
            .binarize(threshold=XP_BINARIZE_THRESHOLD)
            .invert()
        )
        xp_proc = xp_editor.image
        xp_str = await self.ocr.recognize_text(
            xp_proc, ps_mode="SINGLE_LINE", whitelist="0123456789."
        )
        component_count = xp_editor.count_connected_components(
            foreground_threshold=XP_FOREGROUND_THRESHOLD,
            min_area=XP_MIN_COMPONENT_AREA,
        )
        if xp_str is None:
            return XPExtractionDiagnostics(
                xp_roi=xp_image,
                xp_processed=xp_proc,
                ocr_text=None,
                parsed_xp=None,
                xp=None,
                validation_error=None,
                xp_processed_connected_component_count=component_count,
            )
        parsed_xp, validation_error = parse_xp_ocr_text(xp_str)
        if validation_error is not None or parsed_xp is None:
            return XPExtractionDiagnostics(
                xp_roi=xp_image,
                xp_processed=xp_proc,
                ocr_text=xp_str,
                parsed_xp=None,
                xp=None,
                validation_error=validation_error,
                xp_processed_connected_component_count=component_count,
            )
        validation_error = validate_xp_processed_component_count(
            component_count
        )
        if validation_error is not None:
            return XPExtractionDiagnostics(
                xp_roi=xp_image,
                xp_processed=xp_proc,
                ocr_text=xp_str,
                parsed_xp=parsed_xp,
                xp=None,
                validation_error=validation_error,
                xp_processed_connected_component_count=component_count,
            )
        try:
            xp = XP(parsed_xp)
        except Exception as exc:
            return XPExtractionDiagnostics(
                xp_roi=xp_image,
                xp_processed=xp_proc,
                ocr_text=xp_str,
                parsed_xp=parsed_xp,
                xp=None,
                validation_error=str(exc),
                xp_processed_connected_component_count=component_count,
            )
        return XPExtractionDiagnostics(
            xp_roi=xp_image,
            xp_processed=xp_proc,
            ocr_text=xp_str,
            parsed_xp=parsed_xp,
            xp=xp,
            validation_error=None,
            xp_processed_connected_component_count=component_count,
        )

    async def detect_session_start(self, frame: Frame) -> bool:
        return await self.matcher.match("battle_start", frame)

    async def detect_session_abort(self, frame: Frame) -> bool:
        return await self.matcher.match("battle_abort", frame)

    async def detect_communication_error(self, frame: Frame) -> bool:
        return await self.matcher.match("battle_communication_error", frame)

    async def detect_session_finish(self, frame: Frame) -> bool:
        return await self.matcher.match("battle_finish", frame)

    async def detect_session_finish_end(self, frame: Frame) -> bool:
        return await self.detect_session_judgement(frame)

    async def detect_session_judgement(self, frame: Frame) -> bool:
        return await self.matcher.match("battle_judgement_latter_half", frame)

    async def extract_session_judgement(
        self, frame: Frame
    ) -> Optional[Judgement]:
        """勝敗画面から勝敗を取得する。"""
        judgement = await self.matcher.matched_name("battle_judgements", frame)
        return Judgement(judgement) if judgement else None

    async def detect_session_result(self, frame: Frame) -> bool:
        return await self.matcher.match("battle_result", frame)

    async def extract_session_result(
        self, frame: Frame
    ) -> Optional[BattleResult]:
        """結果画面から試合結果を抽出する (可能な部分を並列化)。"""
        match = await self.extract_battle_match(frame)
        if match is None:
            return None

        # ルール / ステージ / キルレコード / 表彰 を並列取得
        rule_task = asyncio.create_task(self.extract_battle_rule(frame))
        stage_task = asyncio.create_task(self.extract_battle_stage(frame))
        kill_task = asyncio.create_task(
            self.extract_battle_kill_record(frame, match)
        )
        medal_task = asyncio.create_task(self.extract_battle_medals(frame))

        rule, stage, kill_record, medal_counts = await asyncio.gather(
            rule_task, stage_task, kill_task, medal_task
        )

        if rule is None:
            return None
        if stage is None:
            return None
        if kill_record is None:
            return None
        result = BattleResult(
            match=match,
            rule=rule,
            stage=stage,
            kill=kill_record[0],
            death=kill_record[1],
            special=kill_record[2],
            gold_medals=medal_counts[0],
            silver_medals=medal_counts[1],
        )
        return result

    async def extract_battle_medals(self, frame: Frame) -> Tuple[int, int]:
        try:
            return await self.medal_recognizer.count_medals(frame)
        except Exception:
            return 0, 0

    async def extract_battle_match(self, frame: Frame) -> Optional[Match]:
        """バトルマッチの種類を取得する。"""
        match_name = await self.matcher.matched_name("battle_matches", frame)
        return Match(match_name) if match_name else None

    async def extract_battle_rule(self, frame: Frame) -> Optional[Rule]:
        """バトルルールを取得する。"""
        rule_name = await self.matcher.matched_name("battle_rules", frame)
        return Rule(rule_name) if rule_name else None

    async def extract_battle_stage(self, frame: Frame) -> Optional[Stage]:
        """バトルステージを取得する。"""
        stage_name = await self.matcher.matched_name("battle_stages", frame)
        return Stage(stage_name) if stage_name else None

    async def extract_battle_kill_record(
        self, frame: Frame, match: Match
    ) -> Optional[tuple[int, int, int]]:
        """キルレコードを取得する。"""
        return await self._kill_record_extractor.extract_battle_kill_record(
            frame, match
        )
