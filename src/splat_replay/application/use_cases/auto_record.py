"""自動録画ユースケース。"""

from __future__ import annotations

import time
import datetime
from typing import Callable, List

import cv2
import numpy as np

from splat_replay.application.interfaces import (
    VideoRecorder,
    FrameAnalyzerPort,
    SpeechTranscriberPort,
    PowerPort,
    VideoAssetRepository,
)
from splat_replay.domain.services.state_machine import (
    Event,
    State,
    StateMachine,
)
from splat_replay.shared.config import OBSSettings
from splat_replay.shared.logger import get_logger
from splat_replay.domain.models import (
    RateBase,
    Result,
    RecordingMetadata,
    VideoAsset,
)


class AutoRecordUseCase:
    """電源OFFまで自動録画を行い、VideoAsset の一覧を返す。"""

    def __init__(
        self,
        recorder: VideoRecorder,
        analyzer: FrameAnalyzerPort,
        transcriber: SpeechTranscriberPort,
        power: PowerPort,
        state_machine: StateMachine,
        obs_settings: OBSSettings,
        asset_repo: VideoAssetRepository,
    ) -> None:
        self.recorder = recorder
        self.analyzer = analyzer
        self.transcriber = transcriber
        self.power = power
        self.sm = state_machine
        self.settings = obs_settings
        self.asset_repo = asset_repo
        self.pending: List[VideoAsset] = []
        self.logger = get_logger()
        self._resume_trigger: Callable[[np.ndarray], bool] | None = None
        self.finish: bool = False
        self._battle_started_at = 0.0
        self._matching_started_at: datetime.datetime | None = None
        self.rate: RateBase | None = None
        self.judgement: str | None = None
        self.result: Result | None = None
        self.result_screenshot: np.ndarray | None = None

    def _start(self) -> None:
        self.recorder.start()
        self.transcriber.start()
        self._battle_started_at = time.time()

    def _stop(self, save: bool = True) -> None:
        video = self.recorder.stop()
        subtitle = self.transcriber.stop()
        if save:
            metadata = RecordingMetadata(
                started_at=self._matching_started_at,
                match=self.result.match if self.result else None,
                rule=self.result.rule if self.result else None,
                stage=self.result.stage if self.result else None,
                rate=self.rate,
                judgement=self.judgement,
                kill=self.result.kill if self.result else None,
                death=self.result.death if self.result else None,
                special=self.result.special if self.result else None,
            )
            asset = self.asset_repo.save_recording(
                video,
                subtitle,
                self.result_screenshot,
                metadata,
            )
            self.logger.info(
                "録画終了",
                video=str(asset.video),
                start_at=self._matching_started_at,
            )
            self.pending.append(asset)
        self.finish = False
        self._battle_started_at = 0.0
        self._matching_started_at = None
        self.rate = None
        self.judgement = None
        self.result = None
        self.result_screenshot = None
        self.analyzer.reset()

    def _cancel(self) -> None:
        self._stop(save=False)

    def _pause(self, resume_trigger: Callable[[np.ndarray], bool]) -> None:
        self.recorder.pause()
        self.transcriber.pause()
        self._resume_trigger = resume_trigger

    def _resume(self) -> None:
        self.recorder.resume()
        self.transcriber.resume()

    def _update_power_off_count(
        self, frame: np.ndarray, off_count: int, last_check: float
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

    def _handle_power_off(self) -> None:
        if self.sm.state in {State.RECORDING, State.PAUSED}:
            self._stop()
            self.sm.handle(Event.POSTGAME_DETECTED)
        self.power.sleep()

    def _handle_standby(self, frame: np.ndarray) -> None:
        if self._matching_started_at is None:
            if self.analyzer.detect_match_select(frame):
                rate = self.analyzer.extract_rate(frame)
                if not isinstance(rate, type(self.rate)) or rate != self.rate:
                    self.rate = rate
                    self.logger.info("レート取得", rate=str(rate))
                return
            if self.analyzer.detect_matching_start(frame):
                self.logger.info("マッチング開始を検出")
                self._matching_started_at = datetime.datetime.now()
                return
        else:
            if self.analyzer.detect_schedule_change(frame):
                self.logger.info("スケジュール変更を検出、情報をリセット")
                self._cancel()
                return
            if self.analyzer.detect_battle_start(frame):
                self.logger.info("バトル開始を検出")
                self._start()
                self.sm.handle(Event.BATTLE_STARTED)
                return

    def _handle_recording(self, frame: np.ndarray) -> None:
        if not self.finish:
            now = time.time()
            if (
                now - self._battle_started_at <= 60
                and self.analyzer.detect_battle_abort(frame)
            ):
                self.logger.info("バトル中断を検出したため録画を中止")
                self._cancel()
                self.sm.handle(Event.EARLY_ABORT)
                return
            if now - self._battle_started_at >= 600:
                self.logger.info("録画が10分以上続いたため停止")
                self._stop()
                self.sm.handle(Event.POSTGAME_DETECTED)
                return
            if self.analyzer.detect_battle_finish(frame):
                self.logger.info("バトル終了を検出、一時停止")
                self.finish = True
                self._pause(self.analyzer.detect_battle_judgement)
                self.sm.handle(Event.LOADING_DETECTED)
                return
        else:
            if self.analyzer.detect_battle_judgement(frame):
                judgement = self.analyzer.extract_battle_judgement(frame)
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
            if self.analyzer.detect_battle_result(frame):
                self.result = self.analyzer.extract_battle_result(frame)
                self.result_screenshot = frame
                self.logger.info("バトル結果を検出", result=str(self.result))
                self._stop()
                self.sm.handle(Event.POSTGAME_DETECTED)

    def _handle_paused(self, frame: np.ndarray) -> None:
        if self._resume_trigger and self._resume_trigger(frame):
            self.logger.info("録画を再開")
            self._resume()
            self.sm.handle(Event.LOADING_FINISHED)

    def execute(self) -> List[VideoAsset]:
        self.pending.clear()
        self.logger.info("自動録画開始")
        cap = cv2.VideoCapture(self.settings.capture_device_index)
        if not cap.isOpened():
            self.logger.error(
                "キャプチャデバイスを開けません",
                index=self.settings.capture_device_index,
            )
            raise RuntimeError("キャプチャデバイスの取得に失敗しました")
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
        off_count = 0
        last_check = 0.0
        try:
            while True:
                success, frame = cap.read()
                if not success:
                    self.logger.warning("フレーム取得に失敗")
                    raise RuntimeError(
                        "フレームの読み込みに失敗しました。\n他のアプリがカメラを使用していないか確認してください。"
                    )
                off_count, last_check, detected = self._update_power_off_count(
                    frame, off_count, last_check
                )
                if detected:
                    self._handle_power_off()
                    break
                if self.sm.state is State.STANDBY:
                    self._handle_standby(frame)
                elif self.sm.state is State.RECORDING:
                    self._handle_recording(frame)
                elif self.sm.state is State.PAUSED:
                    self._handle_paused(frame)
        finally:
            cap.release()
            if self.sm.state is State.RECORDING:
                self._cancel()
            self.sm.state = State.STANDBY
        return list(self.pending)
