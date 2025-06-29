"""ゲームプレイ全体を自動処理するユースケース。"""

from __future__ import annotations

import time
import datetime
from pathlib import Path
from typing import List, Callable

import cv2
import numpy as np

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
from splat_replay.domain.models import RateBase, Result


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
        self._resume_trigger: Callable[[np.ndarray], bool] | None = None
        self.finish: bool = False
        self._battle_started_at = 0.0
        self._matching_started_at: datetime.datetime | None = None
        self.rate: RateBase | None = None
        self.judgement: str | None = None
        self.result: Result | None = None
        self.result_screenshot: np.ndarray | None = None

    def _start(self) -> None:
        """録画と音声キャプチャを開始する。"""
        self.recorder.start()
        self.transcriber.start()
        self._battle_started_at = time.time()

    def _stop(self, save: bool = True) -> None:
        """録画と音声キャプチャを停止する。"""
        video = self.recorder.stop()
        srt = self.transcriber.stop()

        if save:
            self.logger.info("録画と音声キャプチャを停止", video=video, srt=srt,
                             start_at=self._matching_started_at, rate=str(self.rate), judgement=self.judgement, result=self.result)
            # 動画ファイルに字幕とサムネイル(結果画面)を結合し、ファイル名にマッチング開始時間・レート・判定・結果を含めて、編集待ちフォルダに移動する。
            raise NotImplementedError(
                "動画の編集とアップロード処理は未実装です"
            )

        self.finish = False
        self._battle_started_at = 0.0
        self._matching_started_at = None
        self.rate = None
        self.judgement = None
        self.result = None
        self.result_screenshot = None
        self.analyzer.reset()

    def _cancel(self) -> None:
        """録画と音声キャプチャをキャンセルする。"""
        self._stop(save=False)

    def _pause(self, resume_trigger: Callable[[np.ndarray], bool]) -> None:
        """録画と音声キャプチャを一時停止する。"""
        self.recorder.pause()
        self.transcriber.pause()
        self._resume_trigger = resume_trigger

    def _resume(self) -> None:
        """録画と音声キャプチャを再開する。"""
        self.recorder.resume()
        self.transcriber.resume()

    def _process_pending(self) -> None:
        """溜まっている録画を編集しアップロードする。"""
        self.logger.info("編集待ちの録画を処理中", count=len(self.pending))
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

    def _handle_standby(self, frame: np.ndarray) -> None:
        """STANDBY 状態でのフレーム処理。"""
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
        """RECORDING 状態でのフレーム処理。"""
        if not self.finish:
            now = time.time()
            if (
                now - self._battle_started_at <= 60
                and self.analyzer.detect_battle_abort(frame)
            ):
                self.logger.info("バトル中断を検出したため、録画を中止します")
                self._cancel()
                self.sm.handle(Event.EARLY_ABORT)
                return

            if now - self._battle_started_at >= 600:
                self.logger.info("録画が10分以上続いているため、録画を停止します")
                self._stop()
                self.sm.handle(Event.POSTGAME_DETECTED)
                return

            if self.analyzer.detect_battle_finish(frame):
                self.logger.info("バトル終了を検出したので、録画を一時停止します")
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
                        "バトルジャッジメントを検出", judgement=str(self.judgement)
                    )
                return

            if self.analyzer.detect_loading(frame):
                self.logger.info("ロード画面を検出したので、録画を一時停止します")
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
        """PAUSED 状態でのフレーム処理。"""
        if self._resume_trigger and self._resume_trigger(frame):
            self.logger.info("録画を再開します")
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

            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)

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
                if self.sm.state is State.RECORDING:
                    self._cancel()
                self.sm.state = State.STANDBY
