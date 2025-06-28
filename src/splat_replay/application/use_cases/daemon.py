"""ゲームプレイ全体を自動処理するユースケース。"""

from __future__ import annotations

import time
import datetime
from pathlib import Path
from typing import List

import cv2

from splat_replay.application.interfaces import (
    VideoRecorder,
    FrameAnalyzerPort,
    SpeechTranscriberPort,
    VideoEditorPort,
    UploadPort,
    MetadataExtractorPort,
    PowerPort,
)
from splat_replay.domain.repositories.metadata_repo import MetadataRepository
from splat_replay.domain.services.state_machine import (
    Event,
    State,
    StateMachine,
)
from splat_replay.shared.logger import get_logger
from splat_replay.shared.config import OBSSettings


class DaemonUseCase:
    """ユーザー操作なしで録画からアップロードまでを制御する。"""

    def __init__(
        self,
        recorder: VideoRecorder,
        analyzer: FrameAnalyzerPort,
        transcriber: SpeechTranscriberPort,
        editor: VideoEditorPort,
        uploader: UploadPort,
        extractor: MetadataExtractorPort,
        power: PowerPort,
        metadata_repo: MetadataRepository,
        state_machine: StateMachine,
        obs_settings: OBSSettings,
    ) -> None:
        self.recorder = recorder
        self.analyzer = analyzer
        self.transcriber = transcriber
        self.editor = editor
        self.uploader = uploader
        self.extractor = extractor
        self.power = power
        self.repo = metadata_repo
        self.sm = state_machine
        self.settings = obs_settings
        self.pending: List[Path] = []
        self.logger = get_logger()
        self.rate: int | None = None
        self.finish: bool = False
        self.judgement: str | None = None
        self._battle_started_at = 0.0
        self._matching_started_at: datetime.datetime | None = None

    def _start(self) -> None:
        """録画と音声キャプチャを開始する。"""
        self.recorder.start()
        self.transcriber.start_capture()
        self._battle_started_at = time.time()

    def _stop(self, save: bool = True) -> None:
        """録画と音声キャプチャを停止する。"""
        video = self.recorder.stop()
        audio = self.transcriber.stop_capture()
        _ = self.transcriber.transcribe(audio)

        if save:
            self.pending.append(video)

        self.rate = None
        self.finish = False
        self.judgement = None
        self._battle_started_at = 0.0
        self._matching_started_at = None
        self.analyzer.reset()

    def _cancel(self) -> None:
        """録画と音声キャプチャをキャンセルする。"""
        self._stop(save=False)

    def _pause(self) -> None:
        """録画と音声キャプチャを一時停止する。"""
        self.recorder.pause()
        self.transcriber.stop_capture()

    def _resume(self) -> None:
        """録画と音声キャプチャを再開する。"""
        self.recorder.resume()
        self.transcriber.start_capture()

    def _process_pending(self) -> None:
        """溜まっている録画を編集しアップロードする。"""
        for clip in list(self.pending):
            edited = self.editor.process(clip)
            match = self.extractor.extract_from_video(edited)
            self.repo.save(match)
            video_id = self.uploader.upload(edited)
            _ = video_id
            self.pending.remove(clip)
        self.power.sleep()

    def _update_power_off_count(
        self, frame, off_count: int, last_check: float
    ) -> tuple[int, float, bool]:
        """フレームから電源OFF判定を行い、カウント・時刻・確定判定を返す。"""
        now = time.time()
        detected = False
        if now - last_check >= 10:
            last_check = now
            if self.analyzer.detect_power_off(frame):
                off_count += 1
                self.logger.info("電源 OFF を検出", count=off_count)
            else:
                off_count = 0
            if off_count >= 6:
                detected = True
        return off_count, last_check, detected

    def _handle_power_off(self) -> None:
        """電源 OFF が確定した際の処理。"""
        if self.sm.state in {State.RECORDING, State.PAUSED}:
            self._stop()
            self.sm.handle(Event.POSTGAME_DETECTED)
        self._process_pending()

    def _handle_standby(self, frame) -> None:
        """STANDBY 状態でのフレーム処理。"""
        if self._matching_started_at is None:
            if self.analyzer.detect_match_select(frame):
                rate = self.analyzer.extract_rate(frame)
                if rate is not None and rate != self.rate:
                    self.rate = rate
                    self.logger.info("レート取得", rate=rate)
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

    def _handle_recording(self, frame) -> None:
        """RECORDING 状態でのフレーム処理。"""
        if not self.finish:
            now = time.time()
            if (
                now - self._battle_started_at <= 60
                and self.analyzer.detect_battle_abort(frame)
            ):
                self.logger.info("バトル中断を検出")
                self._cancel()
                self.sm.handle(Event.EARLY_ABORT)
                return

            if now - self._battle_started_at >= 600:
                self.logger.info("バトルが長すぎるため中断")
                self._stop()
                self.sm.handle(Event.POSTGAME_DETECTED)
                return

            if self.analyzer.detect_battle_finish(frame):
                self.logger.info("バトル終了を検出")
                self.finish = True
                self._pause()
                self.sm.handle(Event.LOADING_DETECTED)
                return

        else:
            if self.analyzer.detect_loading(frame):
                self.logger.info("ロード画面を検出")
                self._pause()
                self.sm.handle(Event.LOADING_DETECTED)
                return

            if self.analyzer.detect_battle_result(frame):
                self.logger.info("バトル結果を検出")
                self.result = self.analyzer.extract_battle_result(frame)
                self._stop()
                self.sm.handle(Event.POSTGAME_DETECTED)

    def _handle_paused(self, frame) -> None:
        """PAUSED 状態でのフレーム処理。"""
        if self.analyzer.detect_battle_judgement(frame):
            self.logger.info("バトルジャッジメントを検出")
            self.judgement = self.analyzer.extract_battle_judgement(frame)
            self._resume()
            self.sm.handle(Event.LOADING_FINISHED)
            return

        if self.analyzer.detect_loading_end(frame):
            self.logger.info("ロード終了を検出")
            self._resume()
            self.sm.handle(Event.LOADING_FINISHED)
            return

    def execute(self) -> None:
        """電源 OFF を監視しつつ自動録画を繰り返す。PC がスリープしたら最初から再開する."""
        while True:
            self.logger.info("デーモン開始")

            cap = cv2.VideoCapture(self.settings.capture_device_index)
            if not cap.isOpened():
                self.logger.error(
                    "キャプチャデバイスを開けません",
                    index=self.settings.capture_device_index,
                )
                raise RuntimeError("キャプチャデバイスの取得に失敗しました")

            off_count = 0
            last_check = 0.0
            try:
                while True:
                    success, frame = cap.read()
                    if not success:
                        self.logger.warning("フレーム取得に失敗しました")
                        raise RuntimeError(
                            "フレームの読み込みに失敗しました。\n他のアプリケーションがカメラを使用していないか確認してください。"
                        )

                    off_count, last_check, detected = (
                        self._update_power_off_count(
                            frame, off_count, last_check
                        )
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
                self._cancel()
                self.sm.state = State.STANDBY
