import datetime
import time
from typing import Callable, Optional

from splat_replay.shared.logger import get_logger
from splat_replay.domain.models import Frame, RateBase, Result, RecordingMetadata, GameMode
from splat_replay.domain.services import (
    FrameAnalyzer,
    Event,
    State,
    StateMachine
)
from splat_replay.application.interfaces import (
    CapturePort,
    VideoRecorder,
    SpeechTranscriberPort,
    VideoAssetRepository,
)


class AutoRecorder:
    """電源OFFまで自動で録画を行うサービス。"""

    def __init__(
        self,
        recorder: VideoRecorder,
        analyzer: FrameAnalyzer,
        transcriber: SpeechTranscriberPort,
        state_machine: StateMachine,
        asset_repo: VideoAssetRepository,
        capture: CapturePort,
    ) -> None:
        self.recorder = recorder
        self.analyzer = analyzer
        self.transcriber = transcriber
        self.sm = state_machine
        self.capture = capture
        self.asset_repo = asset_repo
        self.logger = get_logger()
        self._resume_trigger: Callable[[Frame], bool] | None = None
        self.game_mode: GameMode | None = None
        self.rate: RateBase | None = None
        self.matching_started_at: datetime.datetime | None = None
        self.battle_started_at = 0.0
        self.finish: bool = False
        self.judgement: str | None = None
        self.result: Result | None = None
        self.result_screenshot: Frame | None = None

    def _start(self) -> None:
        self.recorder.start()
        self.transcriber.start()
        self.battle_started_at = time.time()

    def _stop(self, frame: Optional[Frame] = None, save: bool = True) -> None:
        video = self.recorder.stop()
        subtitle = self.transcriber.stop()

        if frame is not None and self.game_mode:
            self.result = self.analyzer.extract_session_result(
                frame, self.game_mode)
            self.result_screenshot = frame
            self.logger.info("バトル結果を検出", result=str(self.result))

        if save:
            if self.matching_started_at is None:
                raise RuntimeError("マッチング開始時刻が設定されていません。")

            metadata = RecordingMetadata(
                started_at=self.matching_started_at,
                rate=self.rate,
                judgement=self.judgement,
                result=self.result,
            )
            asset = self.asset_repo.save_recording(
                video, subtitle, self.result_screenshot, metadata
            )
            self.logger.info(
                "録画終了", video=str(asset.video), start_at=self.matching_started_at
            )

        # 続けてプレイすることがあるので、ゲームモードはここでリセットしない
        self.rate = None
        self.matching_started_at = None
        self.battle_started_at = 0.0
        self.finish = False
        self.judgement = None
        self.result = None
        self.result_screenshot = None

    def _cancel(self) -> None:
        self._stop(save=False)

    def _pause(self, resume_trigger: Callable[[Frame], bool]) -> None:
        self.recorder.pause()
        self.transcriber.pause()
        self._resume_trigger = resume_trigger

    def _resume(self) -> None:
        self.recorder.resume()
        self.transcriber.resume()

    def manual_start(self) -> None:
        """手動で録画を開始する。"""
        if self.sm.state is not State.STANDBY:
            return
        self.matching_started_at = datetime.datetime.now()
        self._start()
        self.sm.handle(Event.MANUAL_START)

    def manual_stop(self) -> None:
        """手動で録画を停止する。"""
        if self.sm.state in {State.RECORDING, State.PAUSED}:
            self._stop()
            self.sm.handle(Event.MANUAL_STOP)

    def manual_pause(self) -> None:
        """手動で録画を一時停止する。"""
        if self.sm.state is State.RECORDING:
            self._pause(lambda _frame: False)
            self.sm.handle(Event.MANUAL_PAUSE)

    def manual_resume(self) -> None:
        """手動で録画を再開する。"""
        if self.sm.state is State.PAUSED:
            self._resume()
            self.sm.handle(Event.MANUAL_RESUME)

    def _update_power_off_count(
        self, frame: Frame, off_count: int, last_check: float
    ) -> tuple[int, float, bool]:
        now = time.time()
        detected = False
        if now - last_check >= 10:
            last_check = now
            if self.analyzer.detect_power_off(frame):
                off_count += 1
                self.logger.info("電源OFFを検出", count=off_count)
            else:
                off_count = 0
            if off_count >= 6:
                detected = True
        return off_count, last_check, detected

    def _handle_standby(self, frame: Frame) -> None:
        if self.matching_started_at is None:
            if self.analyzer.detect_match_select(frame):
                if self.game_mode is None:
                    self.game_mode = self.analyzer.extract_game_mode(frame)
                    self.logger.info("ゲームモード取得", mode=str(self.game_mode))

                if self.game_mode is not None:
                    rate = self.analyzer.extract_rate(frame, self.game_mode)
                    if rate is not None and (not isinstance(rate, type(self.rate)) or rate != self.rate):
                        self.rate = rate
                        self.logger.info("レート取得", rate=str(rate))

            if self.analyzer.detect_matching_start(frame):
                self.logger.info("マッチング開始を検出")
                self.matching_started_at = datetime.datetime.now()
                return
        else:
            if self.analyzer.detect_schedule_change(frame):
                self.logger.info("スケジュール変更を検出、情報をリセット")
                self._cancel()
                return
            if self.game_mode and self.analyzer.detect_session_start(frame, self.game_mode):
                self.logger.info("バトル開始を検出")
                self._start()
                self.sm.handle(Event.BATTLE_STARTED)
                return

    def _handle_recording(self, frame: Frame) -> None:
        if self.game_mode is None:
            raise RuntimeError("ゲームモードが設定されていません。")

        if not self.finish:
            now = time.time()
            if (
                now - self.battle_started_at <= 60
                and self.analyzer.detect_session_abort(frame, self.game_mode)
            ):
                self.logger.info("バトル中断を検出したため録画を中止")
                self._cancel()
                self.sm.handle(Event.EARLY_ABORT)
                return
            if now - self.battle_started_at >= 600:
                self.logger.info("録画が10分以上続いたため停止")
                self._stop()
                self.sm.handle(Event.TIME_OUT)
                return
            if self.analyzer.detect_session_finish(frame, self.game_mode):
                self.logger.info("バトル終了を検出、一時停止")
                self.finish = True
                mode = self.game_mode
                self._pause(
                    lambda x: self.analyzer.detect_session_judgement(x, mode))
                self.sm.handle(Event.LOADING_DETECTED)
                return
        else:
            if self.analyzer.detect_session_judgement(frame, self.game_mode):
                judgement = self.analyzer.extract_session_judgement(
                    frame, self.game_mode)
                if judgement is not None and self.judgement is None:
                    self.judgement = judgement
                    self.logger.info("バトルジャッジメント取得", judgement=str(judgement))
                return
            if self.analyzer.detect_loading(frame):
                self.logger.info("ロード画面を検出、一時停止")
                self._pause(self.analyzer.detect_loading_end)
                self.sm.handle(Event.LOADING_DETECTED)
                return
            if self.analyzer.detect_session_result(frame, self.game_mode):
                self._stop(frame)
                self.sm.handle(Event.BATTLE_ENDED)

    def _handle_paused(self, frame: Frame) -> None:
        if self._resume_trigger and self._resume_trigger(frame):
            self.logger.info("録画を再開")
            self._resume()
            self.sm.handle(Event.LOADING_FINISHED)

    def execute(self) -> None:
        self.logger.info("自動録画開始")
        off_count = 0
        last_check = 0.0
        try:
            self.logger.info("🎮🎮🎮 Let's play! 🎮🎮🎮")
            while True:
                frame = self.capture.capture()
                if frame is None:
                    self.logger.warning("フレーム取得に失敗")
                    raise RuntimeError(
                        "フレームの読み込みに失敗しました。\n他のアプリがカメラを使用していないか確認してください。"
                    )
                off_count, last_check, detected = self._update_power_off_count(
                    frame, off_count, last_check
                )
                if detected:
                    break
                if self.sm.state is State.STANDBY:
                    self._handle_standby(frame)
                elif self.sm.state is State.RECORDING:
                    self._handle_recording(frame)
                elif self.sm.state is State.PAUSED:
                    self._handle_paused(frame)
        finally:
            self.logger.info("自動録画終了")
            self.capture.close()
            if self.sm.state is not State.STANDBY:
                self._cancel()
            self.recorder.close()
