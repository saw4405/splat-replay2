"""Standby phase handler.

マッチング前の待機状態で、ゲームモード・レート・マッチング開始を検出する。
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime

from splat_replay.application.interfaces import (
    EventBusPort,
    LoggerPort,
    XPDetectionDiagnosticsPort,
)
from splat_replay.application.interfaces.xp_detection_diagnostics import (
    XPDetectionDiagnosticsRecord,
)
from splat_replay.application.metadata import recording_metadata_to_dict
from splat_replay.application.services.recording.commands import (
    RecordingCommand,
)
from splat_replay.application.services.recording.recording_context import (
    RecordingContext,
)
from splat_replay.domain.events import (
    BattleMatchingStarted,
    RecordingMetadataUpdated,
)
from splat_replay.domain.models import (
    Frame,
    GameMode,
    Match,
    RateBase,
    XP,
    as_frame,
)
from splat_replay.domain.services import FrameAnalyzer, RecordState

X_MATCH_SELECT_ROI = (280, 390, 20, 20)


@dataclass(frozen=True)
class _RateDetection:
    match: Match | None
    rate: RateBase | None


class StandbyPhaseHandler:
    """STANDBY フェーズの処理。"""

    def __init__(
        self,
        analyzer: FrameAnalyzer,
        logger: LoggerPort,
        event_bus: EventBusPort,
        xp_detection_diagnostics: XPDetectionDiagnosticsPort | None = None,
    ):
        self.analyzer = analyzer
        self.logger = logger
        self.event_bus = event_bus
        self._xp_detection_diagnostics = xp_detection_diagnostics
        self._last_xp_candidate: float | None = None
        self._same_xp_candidate_count = 0

    async def handle(
        self, frame: Frame, ctx: RecordingContext, state: RecordState
    ) -> RecordingCommand:
        """STANDBY フェーズの処理を実行する。"""
        md = ctx.metadata
        match_select_detected = await self.analyzer.detect_match_select(frame)
        matching_start_detected = await self.analyzer.detect_matching_start(
            frame
        )

        if match_select_detected:
            metadata_updated = False
            updates: dict[str, object] = {}

            detected_mode = await self.analyzer.extract_game_mode(frame)
            if detected_mode is not None and detected_mode != md.game_mode:
                updates["game_mode"] = detected_mode
                metadata_updated = True
                self.logger.info("ゲームモード取得", mode=str(detected_mode))

            rate_detection = await self._extract_rate_with_diagnostics(
                frame=frame,
                ctx=ctx,
                state=state,
                detected_mode=detected_mode,
                match_select_detected=match_select_detected,
                matching_start_detected=matching_start_detected,
            )
            if (
                rate_detection.match is not None
                and rate_detection.rate is not None
            ):
                ctx = ctx.with_rate_candidate(
                    rate_detection.match, rate_detection.rate
                )
                self.logger.info(
                    "レート候補を記録",
                    match=str(rate_detection.match),
                    rate=str(rate_detection.rate),
                )

            if metadata_updated:
                ctx = replace(ctx, metadata=replace(ctx.metadata, **updates))
                self.event_bus.publish_domain_event(
                    RecordingMetadataUpdated(
                        metadata=recording_metadata_to_dict(ctx.metadata)
                    )
                )

        if matching_start_detected:
            self.logger.info("マッチング開始を検知")

            ctx = replace(
                ctx,
                metadata=replace(ctx.metadata, started_at=datetime.now()),
            )

            event = BattleMatchingStarted(
                game_mode=str(ctx.metadata.game_mode)
                if ctx.metadata.game_mode
                else "unknown",
                rate=str(ctx.metadata.rate) if ctx.metadata.rate else None,
            )
            self.event_bus.publish_domain_event(event)

            self.event_bus.publish_domain_event(
                RecordingMetadataUpdated(
                    metadata=recording_metadata_to_dict(ctx.metadata)
                )
            )

        return RecordingCommand.none(ctx)

    async def _extract_rate_with_diagnostics(
        self,
        *,
        frame: Frame,
        ctx: RecordingContext,
        state: RecordState,
        detected_mode: GameMode | None,
        match_select_detected: bool,
        matching_start_detected: bool,
    ) -> _RateDetection:
        mode = detected_mode or ctx.metadata.game_mode
        detected_match = await self.analyzer.extract_match_select(frame, mode)
        if detected_match is None:
            return _RateDetection(None, None)

        if not self._xp_diagnostics_enabled():
            return _RateDetection(
                detected_match,
                await self.analyzer.extract_rate_for_match(
                    frame, mode, detected_match
                ),
            )
        if mode is not GameMode.BATTLE:
            return _RateDetection(
                detected_match,
                await self.analyzer.extract_rate_for_match(
                    frame, mode, detected_match
                ),
            )

        if detected_match is not Match.X:
            return _RateDetection(
                detected_match,
                await self.analyzer.extract_rate_for_match(
                    frame, mode, detected_match
                ),
            )

        try:
            diagnostics = await self.analyzer.extract_xp_diagnostics(frame)
        except Exception as exc:
            self.logger.warning(
                "XP 検出診断の抽出に失敗しました",
                error=str(exc),
            )
            return _RateDetection(
                detected_match,
                await self.analyzer.extract_rate_for_match(
                    frame, mode, detected_match
                ),
            )
        if diagnostics is None:
            return _RateDetection(
                detected_match,
                await self.analyzer.extract_rate_for_match(
                    frame, mode, detected_match
                ),
            )

        detected_rate = diagnostics.xp
        previous_candidate = self._last_xp_candidate
        same_candidate_count = self._update_xp_candidate_state(
            diagnostics.parsed_xp
        )
        delta_from_previous_candidate = self._delta(
            diagnostics.parsed_xp, previous_candidate
        )

        self._record_xp_diagnostics(
            frame=frame,
            ctx=ctx,
            state=state,
            detected_mode=detected_mode,
            detected_match=detected_match,
            match_select_detected=match_select_detected,
            matching_start_detected=matching_start_detected,
            ocr_text=diagnostics.ocr_text,
            parsed_xp=diagnostics.parsed_xp,
            validation_error=diagnostics.validation_error,
            accepted_xp=detected_rate,
            previous_candidate_xp=previous_candidate,
            delta_from_previous_candidate_xp=delta_from_previous_candidate,
            same_candidate_count=same_candidate_count,
            metadata_will_update=False,
            xp_roi=diagnostics.xp_roi,
            xp_processed=diagnostics.xp_processed,
            xp_processed_connected_component_count=(
                diagnostics.xp_processed_connected_component_count
            ),
        )
        return _RateDetection(detected_match, detected_rate)

    def _xp_diagnostics_enabled(self) -> bool:
        return (
            self._xp_detection_diagnostics is not None
            and self._xp_detection_diagnostics.is_enabled()
        )

    def _record_xp_diagnostics(
        self,
        *,
        frame: Frame,
        ctx: RecordingContext,
        state: RecordState,
        detected_mode: GameMode | None,
        detected_match: Match | None,
        match_select_detected: bool,
        matching_start_detected: bool,
        ocr_text: str | None,
        parsed_xp: float | None,
        validation_error: str | None,
        accepted_xp: XP | None,
        previous_candidate_xp: float | None,
        delta_from_previous_candidate_xp: float | None,
        same_candidate_count: int,
        metadata_will_update: bool,
        xp_roi: Frame,
        xp_processed: Frame,
        xp_processed_connected_component_count: int | None,
    ) -> None:
        diagnostics = self._xp_detection_diagnostics
        if diagnostics is None:
            return

        previous_rate = ctx.metadata.rate
        previous_xp = (
            previous_rate.xp if isinstance(previous_rate, XP) else None
        )
        record = XPDetectionDiagnosticsRecord(
            timestamp=datetime.now(),
            phase=ctx.phase(state).name,
            record_state=state.name,
            match_select_detected=match_select_detected,
            detected_game_mode=(
                detected_mode.name if detected_mode is not None else None
            ),
            detected_match=(
                detected_match.name if detected_match is not None else None
            ),
            matching_start_detected=matching_start_detected,
            ocr_text=ocr_text,
            parsed_xp=parsed_xp,
            validation_error=validation_error,
            accepted_xp=str(accepted_xp) if accepted_xp is not None else None,
            previous_rate=str(previous_rate) if previous_rate else None,
            previous_xp=previous_xp,
            delta_from_previous_xp=self._delta(parsed_xp, previous_xp),
            previous_candidate_xp=previous_candidate_xp,
            delta_from_previous_candidate_xp=(
                delta_from_previous_candidate_xp
            ),
            same_candidate_count=same_candidate_count,
            metadata_will_update=metadata_will_update,
            xp_roi=xp_roi,
            xp_processed=xp_processed,
            xp_processed_connected_component_count=(
                xp_processed_connected_component_count
            ),
            x_select_roi=self._crop_x_match_select_roi(frame),
        )
        try:
            diagnostics.record(record)
        except Exception as exc:
            self.logger.warning(
                "XP 検出診断の保存に失敗しました",
                error=str(exc),
            )

    def _update_xp_candidate_state(self, parsed_xp: float | None) -> int:
        if parsed_xp is None:
            self._last_xp_candidate = None
            self._same_xp_candidate_count = 0
            return 0
        if self._last_xp_candidate == parsed_xp:
            self._same_xp_candidate_count += 1
        else:
            self._same_xp_candidate_count = 1
        self._last_xp_candidate = parsed_xp
        return self._same_xp_candidate_count

    @staticmethod
    def _should_update_rate(
        detected_rate: RateBase | None, current_rate: RateBase | None
    ) -> bool:
        if detected_rate is None:
            return False
        return (
            not isinstance(detected_rate, type(current_rate))
            or detected_rate != current_rate
        )

    @staticmethod
    def _delta(current: float | None, previous: float | None) -> float | None:
        if current is None or previous is None:
            return None
        return current - previous

    @staticmethod
    def _crop_x_match_select_roi(frame: Frame) -> Frame | None:
        x, y, width, height = X_MATCH_SELECT_ROI
        if frame.shape[0] < y + height or frame.shape[1] < x + width:
            return None
        return as_frame(frame[y : y + height, x : x + width].copy())
