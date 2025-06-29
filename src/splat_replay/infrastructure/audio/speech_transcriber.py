"""音声認識サービス。"""

from __future__ import annotations

from typing import Optional, List, cast, Tuple
import queue
import threading
import time

import speech_recognition as sr

from .stopwatch import StopWatch
from .segment import Segment
from splat_replay.application.interfaces import SpeechTranscriberPort
from splat_replay.infrastructure.adapters.integrated_speech_recognition import IntegratedSpeechRecognizer
from splat_replay.shared.config import SpeechTranscriberSettings
from splat_replay.shared.logger import get_logger


class SpeechTranscriber(SpeechTranscriberPort):
    """文字起こし処理を提供する。"""
    LISTEN_TIMEOUT: int = 1

    @staticmethod
    def find_microphone(device_name: str) -> Optional[int]:
        for index, name in enumerate(sr.Microphone.list_microphone_names()):
            if device_name.lower() in name.lower():
                return index
        return None

    def __init__(self, settings: SpeechTranscriberSettings):
        microphone_index = self.find_microphone(settings.mic_device_name)
        if microphone_index is None:
            raise ValueError("マイクが見つかりません")
        self._microphone = sr.Microphone(device_index=microphone_index)
        self._logger = get_logger()
        self.phrase_time_limit = settings.phrase_time_limit
        self._speech_recognizer = IntegratedSpeechRecognizer(settings)
        self._stopwatch = StopWatch()
        self._recognizer = sr.Recognizer()
        self._is_paused: bool = False
        self._segments: List[Segment] = []
        self._audio_queue: queue.Queue[Tuple[sr.AudioData,
                                             float, float]] = queue.Queue()
        self._recording_event = threading.Event()
        self._recording_thread: Optional[threading.Thread] = None
        self._recognition_thread: Optional[threading.Thread] = None

    def _listen_for_audio(self, source) -> Optional[sr.AudioData]:
        try:
            audio = self._recognizer.listen(
                source,
                timeout=self.LISTEN_TIMEOUT,
                phrase_time_limit=self.phrase_time_limit
            )
            # stream=Falseの場合、audioは常に sr.AudioDataとなる
            return cast(sr.AudioData, audio)
        except sr.WaitTimeoutError:
            return None
        except Exception as e:
            self._logger.error(f"リスニングエラー: {e}")
            return None

    def _recording_loop(self):
        with self._microphone as source:
            self._recognizer.adjust_for_ambient_noise(source)
            while not self._recording_event.is_set():
                if self._is_paused:
                    time.sleep(0.1)
                    continue

                audio = self._listen_for_audio(source)
                if audio is None:
                    continue

                elapsed_time = self._stopwatch.elapsed()
                duration = self.get_audio_duration(audio)
                start = max(elapsed_time - duration, 0)
                end = elapsed_time

                self._audio_queue.put((audio, start, end))

    def _recognition_loop(self):
        while not self._recording_event.is_set():
            if self._audio_queue.empty():
                time.sleep(0.1)
                continue

            audio, start, end = self._audio_queue.get(timeout=1)
            result = self._speech_recognizer.recognize(audio)
            if result is None:
                continue

            self._segments.append(Segment(start, end, result))

    def start(self):
        self._stopwatch.reset()
        self._stopwatch.start()
        self._recording_event.clear()
        self._segments.clear()
        self._recording_thread = threading.Thread(
            target=self._recording_loop, daemon=True)
        self._recognition_thread = threading.Thread(
            target=self._recognition_loop, daemon=True)
        self._recording_thread.start()
        self._recognition_thread.start()

    def pause(self):
        if not self._is_paused:
            self._stopwatch.pause()
            self._is_paused = True

    def resume(self):
        if self._is_paused:
            self._stopwatch.resume()
            self._is_paused = False

    def stop(self) -> str:
        self._recording_event.set()
        self._stopwatch.stop()
        if self._recording_thread:
            self._recording_thread.join()
        if self._recognition_thread:
            self._recognition_thread.join()

        srt_content: List[str] = []
        for index, segment in enumerate(self._segments, 1):
            start = self.format_timedelta(segment.start)
            end = self.format_timedelta(segment.end)
            text = segment.text

            srt_content.append(f"{index}\n{start} --> {end}\n{text}\n\n")

        return "\n".join(srt_content)

    @staticmethod
    def get_audio_duration(audio: sr.AudioData) -> float:
        frames = len(audio.frame_data) / audio.sample_width
        return frames / audio.sample_rate

    @staticmethod
    def format_timedelta(seconds: float) -> str:
        total_seconds = int(seconds)
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        secs = total_seconds % 60
        milliseconds = int((seconds - total_seconds) * 1000)
        return f"{hours:02}:{minutes:02}:{secs:02},{milliseconds:03}"
