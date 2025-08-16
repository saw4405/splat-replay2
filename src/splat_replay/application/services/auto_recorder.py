import datetime
import time
from typing import Awaitable, Callable

from structlog.stdlib import BoundLogger

from splat_replay.application.interfaces import (
    CapturePort,
    RecorderStatus,
    RecorderWithTranscriptionPort,
    VideoAssetRepository,
)
from splat_replay.domain.models import (
    Frame,
    GameMode,
    RateBase,
    RecordingMetadata,
)
from splat_replay.domain.services import (
    FrameAnalyzer,
    RecordEvent,
    RecordState,
    StateMachine,
)


class AutoRecorder:
    def __init__(
        self,
        state_machine: StateMachine,
        capture: CapturePort,
        analyzer: FrameAnalyzer,
        recorder: RecorderWithTranscriptionPort,
        asset_repository: VideoAssetRepository,
        logger: BoundLogger,
    ):
        self.sm = state_machine
        self.capture = capture
        self.analyzer = analyzer
        self.recorder = recorder
        self.asset_repository = asset_repository
        self.logger = logger

        self.recorder.add_status_listener(self.handle_record_state_changed)

        self._resume_trigger: Callable[[Frame], Awaitable[bool]] | None = None
        self.game_mode: GameMode | None = None
        self.rate: RateBase | None = None
        self.matching_started_at: datetime.datetime | None = None
        self.battle_started_at = 0.0
        self.finish: bool = False
        self.judgement: str | None = None
        self.result_frame: Frame | None = None

    async def handle_record_state_changed(self, state: RecorderStatus) -> None:
        if state == "started" and self.sm.state == RecordState.RECORDING:
            return
        if state == "stopped" and self.sm.state == RecordState.STOPPED:
            return
        if state == "paused" and self.sm.state == RecordState.PAUSED:
            return
        if state == "resumed" and self.sm.state == RecordState.RECORDING:
            return
        # 一旦状態確認だけ
        self.logger.error(
            "状態が一致しません。",
            recorder=state,
            state=self.sm.state.name,
        )

    def _reset(self) -> None:
        """録画の状態をリセットする。"""
        # 続けてプレイすることがあるので、ゲームモードはここでリセットせず、ゲームモード取得時に更新するのみ
        self.rate = None
        self.matching_started_at = None
        self.battle_started_at = 0.0
        self.finish = False
        self.judgement = None
        self.result_frame = None

    async def _stop(self) -> None:
        await self.sm.handle(RecordEvent.STOP)
        video, srt = await self.recorder.stop()
        self.logger.info("録画を停止", video=str(video))

        if video is None:
            self.logger.error("録画に失敗しました。")
            return

        if self.result_frame is None or self.game_mode is None:
            self.logger.error(
                "結果フレームまたはゲームモードが設定されていません。"
            )
            return

        result = await self.analyzer.extract_session_result(
            self.result_frame, self.game_mode
        )
        self.logger.info("バトル結果を検出", result=str(result))

        if self.matching_started_at is None:
            self.logger.error("マッチング開始時刻が設定されていません。")
            return

        metadata = RecordingMetadata(
            started_at=self.matching_started_at,
            rate=self.rate,
            judgement=self.judgement,
            result=result,
        )
        asset = self.asset_repository.save_recording(
            video, srt, self.result_frame, metadata
        )
        self.logger.info(
            "録画終了",
            video=str(asset.video),
            start_at=self.matching_started_at,
        )

        self._reset()

    async def execute(self):
        self.logger.info("自動録画開始")
        try:
            await self.recorder.init()
            self.capture.init()

            self.logger.info("🎮🎮🎮 Let's play! 🎮🎮🎮")
            off_count = 0
            last_check = 0.0
            while True:
                frame = self.capture.capture()
                if frame is None:
                    self.logger.warning(
                        "フレームの読み込みに失敗しました。\n他のアプリがカメラを使用していないか確認してください。"
                    )
                    break

                off_count, last_check, detected = await self._detect_power_off(
                    frame, off_count, last_check
                )
                if detected:
                    self.logger.info("電源OFFを検出、録画を停止")
                    break

                if self.sm.state is RecordState.STOPPED:
                    await self._handle_standby(frame)
                elif self.sm.state is RecordState.RECORDING:
                    await self._handle_recording(frame)
                elif self.sm.state is RecordState.PAUSED:
                    await self._handle_paused(frame)

        finally:
            self.capture.close()
            await self.recorder.close()
            self.logger.info("自動録画終了")

    async def _detect_power_off(
        self, frame: Frame, off_count: int, last_check: float
    ) -> tuple[int, float, bool]:
        now = time.time()
        if now - last_check < 10:
            return off_count, last_check, False

        last_check = now
        if await self.analyzer.detect_power_off(frame):
            off_count += 1
            self.logger.info("電源OFFを検出", count=off_count)
        else:
            off_count = 0

        detected = off_count >= 6
        return off_count, last_check, detected

    async def _handle_standby(self, frame: Frame) -> None:
        if self.matching_started_at is None:
            if await self.analyzer.detect_match_select(frame):
                if self.game_mode is None:
                    self.game_mode = await self.analyzer.extract_game_mode(
                        frame
                    )
                    if self.game_mode is not None:
                        self.logger.info(
                            "ゲームモード取得", mode=str(self.game_mode)
                        )

                if self.game_mode is not None:
                    rate = await self.analyzer.extract_rate(
                        frame, self.game_mode
                    )
                    if rate is not None and (
                        not isinstance(rate, type(self.rate))
                        or rate != self.rate
                    ):
                        self.rate = rate
                        self.logger.info("レート取得", rate=str(rate))

            if await self.analyzer.detect_matching_start(frame):
                self.logger.info("マッチング開始を検出")
                self.matching_started_at = datetime.datetime.now()
                return

        else:
            if await self.analyzer.detect_schedule_change(frame):
                self.logger.info("スケジュール変更を検出、情報をリセット")
                self._reset()
                return

            if self.game_mode and await self.analyzer.detect_session_start(
                frame, self.game_mode
            ):
                self.logger.info("バトル開始を検出")
                self.battle_started_at = time.time()
                await self.sm.handle(RecordEvent.START)
                await self.recorder.start()

    async def _handle_recording(self, frame: Frame) -> None:
        if self.game_mode is None:
            raise RuntimeError("ゲームモードが設定されていません。")

        if self.result_frame is None:
            if not self.finish:
                now = time.time()
                if (
                    now - self.battle_started_at <= 60
                    and await self.analyzer.detect_session_abort(
                        frame, self.game_mode
                    )
                ):
                    self.logger.info("バトル中断を検出したため録画を中止")
                    await self.sm.handle(RecordEvent.STOP)
                    await self.recorder.cancel()
                    self._reset()
                    return

                if now - self.battle_started_at >= 600:
                    self.logger.info("録画が10分以上続いたため停止")
                    await self._stop()
                    return

                if await self.analyzer.detect_session_finish(
                    frame, self.game_mode
                ):
                    self.logger.info("バトル終了を検出、一時停止")
                    self.finish = True
                    mode = self.game_mode
                    self._resume_trigger = (
                        lambda frame: self.analyzer.detect_session_judgement(
                            frame, mode
                        )
                    )
                    await self.sm.handle(RecordEvent.PAUSE)
                    await self.recorder.pause()
                    return

            else:
                if await self.analyzer.detect_session_judgement(
                    frame, self.game_mode
                ):
                    judgement = await self.analyzer.extract_session_judgement(
                        frame, self.game_mode
                    )
                    if judgement is not None and self.judgement is None:
                        self.judgement = judgement
                        self.logger.info(
                            "バトルジャッジメント取得",
                            judgement=str(judgement),
                        )
                    return

                if await self.analyzer.detect_loading(frame):
                    self.logger.info("ロード画面を検出、一時停止")
                    self._resume_trigger = self.analyzer.detect_loading_end
                    await self.sm.handle(RecordEvent.PAUSE)
                    await self.recorder.pause()
                    return

                if await self.analyzer.detect_session_result(
                    frame, self.game_mode
                ):
                    self.logger.info("結果画面を検出")
                    self.result_frame = frame
                    return

        else:
            if not await self.analyzer.detect_session_result(
                frame, self.game_mode
            ):
                self.logger.info("結果画面から遷移")
                await self._stop()
                return

    async def _handle_paused(self, frame: Frame) -> None:
        if self._resume_trigger and await self._resume_trigger(frame):
            self.logger.info("録画を再開")
            await self.sm.handle(RecordEvent.RESUME)
            await self.recorder.resume()
