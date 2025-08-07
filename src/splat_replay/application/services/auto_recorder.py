import datetime
import time
from typing import Callable, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from structlog.stdlib import BoundLogger
from splat_replay.domain.models import (
    Frame,
    RateBase,
    Result,
    RecordingMetadata,
    GameMode,
)
from splat_replay.domain.services import (
    FrameAnalyzer,
    Event,
    State,
    StateMachine,
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
        transcriber: Optional[SpeechTranscriberPort],
        state_machine: StateMachine,
        asset_repo: VideoAssetRepository,
        capture: CapturePort,
        logger: BoundLogger,
    ) -> None:
        self.recorder = recorder
        self.analyzer = analyzer
        self.transcriber = transcriber
        self.sm = state_machine
        self.capture = capture
        self.asset_repo = asset_repo
        self.logger = logger
        self._resume_trigger: Callable[[Frame], bool] | None = None
        self.game_mode: GameMode | None = None
        self.rate: RateBase | None = None
        self.matching_started_at: datetime.datetime | None = None
        self.battle_started_at = 0.0
        self.finish: bool = False
        self.judgement: str | None = None

    def _reset(self) -> None:
        """録画の状態をリセットする。"""
        # 続けてプレイすることがあるので、ゲームモードはここでリセットせず、ゲームモード取得時に更新するのみ
        self.rate = None
        self.matching_started_at = None
        self.battle_started_at = 0.0
        self.finish = False
        self.judgement = None

    def _start(self) -> None:
        self.recorder.start()
        if self.transcriber is not None:
            self.transcriber.start()
        self.battle_started_at = time.time()

    def _stop(self, frame: Optional[Frame] = None) -> None:
        def stop_record() -> Tuple[Path, str]:
            time.sleep(1.5)
            video = self.recorder.stop()
            subtitle = (
                self.transcriber.stop() if self.transcriber is not None else ""
            )
            self.logger.info("録画を停止", video=str(video))
            return video, subtitle

        def extract_result(
            frame: Optional[Frame], game_mode: Optional[GameMode]
        ) -> Tuple[Optional[Result], Optional[Frame]]:
            if frame is None or game_mode is None:
                return None, None

            result = self.analyzer.extract_session_result(frame, game_mode)
            if result is None:
                return None, None

            self.logger.info("バトル結果を検出", result=str(result))
            return result, frame

        with ThreadPoolExecutor() as executor:
            future_record = executor.submit(stop_record)
            future_result = executor.submit(
                extract_result, frame, game_mode=self.game_mode
            )
            video, subtitle = future_record.result()
            result, result_screenshot = future_result.result()

        if self.matching_started_at is None:
            raise RuntimeError("マッチング開始時刻が設定されていません。")

        metadata = RecordingMetadata(
            started_at=self.matching_started_at,
            rate=self.rate,
            judgement=self.judgement,
            result=result,
        )
        asset = self.asset_repo.save_recording(
            video, subtitle, result_screenshot, metadata
        )
        self.logger.info(
            "録画終了",
            video=str(asset.video),
            start_at=self.matching_started_at,
        )

        self._reset()

    def _cancel(self) -> None:
        self.recorder.stop()
        self.transcriber.stop() if self.transcriber is not None else ""
        self._reset()

    def _pause(self, resume_trigger: Callable[[Frame], bool]) -> None:
        self.recorder.pause()
        if self.transcriber is not None:
            self.transcriber.pause()
        self._resume_trigger = resume_trigger

    def _resume(self) -> None:
        self.recorder.resume()
        if self.transcriber is not None:
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
                    if self.game_mode is not None:
                        self.logger.info(
                            "ゲームモード取得", mode=str(self.game_mode)
                        )

                if self.game_mode is not None:
                    rate = self.analyzer.extract_rate(frame, self.game_mode)
                    if rate is not None and (
                        not isinstance(rate, type(self.rate))
                        or rate != self.rate
                    ):
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
            if self.game_mode and self.analyzer.detect_session_start(
                frame, self.game_mode
            ):
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
                    lambda x: self.analyzer.detect_session_judgement(x, mode)
                )
                self.sm.handle(Event.LOADING_DETECTED)
                return
        else:
            if self.analyzer.detect_session_judgement(frame, self.game_mode):
                judgement = self.analyzer.extract_session_judgement(
                    frame, self.game_mode
                )
                if judgement is not None and self.judgement is None:
                    self.judgement = judgement
                    self.logger.info(
                        "バトルジャッジメント取得", judgement=str(judgement)
                    )
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
