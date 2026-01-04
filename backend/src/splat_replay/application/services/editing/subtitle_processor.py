"""字幕処理サービス。

責務: VideoAsset から字幕を結合し、音声読み上げを生成する。
"""

from __future__ import annotations

import asyncio
import io
import re
import wave
from array import array
from pathlib import Path
from typing import List, Tuple

from splat_replay.application.interfaces.common import (
    ConfigPort,
    FileSystemPort,
    LoggerPort,
)
from splat_replay.application.interfaces.data import SpeechSynthesisRequest
from splat_replay.application.interfaces.image import SubtitleEditorPort
from splat_replay.application.interfaces.audio import TextToSpeechPort
from splat_replay.application.interfaces.video import (
    VideoAssetRepositoryPort,
    VideoEditorPort,
)
from splat_replay.domain.models import VideoAsset


class SubtitleProcessor:
    """字幕を処理し、音声読み上げを生成するサービス。"""

    def __init__(
        self,
        logger: LoggerPort,
        config: ConfigPort,
        subtitle_editor: SubtitleEditorPort,
        text_to_speech: TextToSpeechPort,
        video_editor: VideoEditorPort,
        repo: VideoAssetRepositoryPort,
        file_system: FileSystemPort,
    ):
        self.logger = logger
        self.config = config
        self.settings = config.get_video_edit_settings()
        self.subtitle_editor = subtitle_editor
        self.text_to_speech = text_to_speech
        self.video_editor = video_editor
        self.repo = repo
        self._file_system = file_system

    async def create_and_embed(
        self, target: Path, group: List[VideoAsset]
    ) -> None:
        """字幕を作成し、音声読み上げを動画に埋め込む。"""
        combined_srt = await self._create_subtitle(target, group)
        if combined_srt:
            await self._embed_subtitle_speech(target, combined_srt)

    async def _create_subtitle(
        self, target: Path, group: List[VideoAsset]
    ) -> str:
        """字幕を作成してファイルに保存する。"""
        subtitles: List[Path] = []
        video_lengths: List[float] = []
        for asset in group:
            if asset.subtitle is None:
                continue
            if not self._file_system.is_file(asset.subtitle):
                continue
            video_length = await self.video_editor.get_video_length(
                asset.video
            )
            if video_length is None:
                self.logger.warning(
                    "動画の長さを取得できませんでした", video=str(asset.video)
                )
                continue
            subtitles.append(asset.subtitle)
            video_lengths.append(video_length)

        combined_srt = await asyncio.to_thread(
            self.subtitle_editor.merge, subtitles, video_lengths
        )
        if combined_srt:
            # 字幕をリポジトリ経由で保存
            await asyncio.to_thread(
                self.repo.save_edited_subtitle, target, combined_srt
            )
        return combined_srt

    async def _embed_subtitle_speech(
        self, target: Path, srt_text: str
    ) -> None:
        """字幕を読み上げ、動画に音声トラックとして追加する。"""
        speech_settings = self.settings.speech
        if not speech_settings.enabled:
            self.logger.info("字幕読み上げは無効化されています")
            return
        if not self.text_to_speech:
            self.logger.warning(
                "テキスト読み上げポートが利用できないためスキップします"
            )
            return
        entries = self._parse_srt(srt_text)
        if not entries:
            self.logger.info("読み上げ対象の字幕がありません")
            return

        segments: list[tuple[float, bytes]] = []
        has_text = False
        for start, _, original_text in entries:
            sanitized = re.sub(r"<[^>]+>", "", original_text)
            normalized = sanitized.replace("\n", " ").strip()
            if not normalized:
                continue
            has_text = True
            request = SpeechSynthesisRequest(
                text=normalized,
                language_code=speech_settings.language_code,
                voice_name=speech_settings.voice_name,
                speaking_rate=speech_settings.speaking_rate,
                pitch=speech_settings.pitch,
                audio_encoding=speech_settings.audio_encoding,
                sample_rate_hz=speech_settings.sample_rate_hz,
                model=speech_settings.model or None,
            )
            try:
                result = await asyncio.to_thread(
                    self.text_to_speech.synthesize, request
                )
            except Exception as exc:  # noqa: BLE001
                self.logger.error(
                    "字幕読み上げ生成に失敗しました",
                    error=str(exc),
                    subtitle=request.text,
                )
                return
            if result.sample_rate_hz != speech_settings.sample_rate_hz:
                self.logger.warning(
                    "サンプルレートが設定と一致しません",
                    expected=speech_settings.sample_rate_hz,
                    actual=result.sample_rate_hz,
                )
            segments.append((start, result.audio))

        if not has_text:
            self.logger.info("読み上げ対象となる字幕テキストがありません")
            return

        if not segments:
            self.logger.info("読み上げ音声の生成結果が空でした")
            return

        narration_path = target.with_name(f"{target.stem}_narration.wav")
        try:
            waveform = await asyncio.to_thread(
                self._compose_wave,
                segments,
                speech_settings.sample_rate_hz,
            )
            if not waveform:
                self.logger.info(
                    "生成された読み上げ波形が空のためスキップします"
                )
                return
            wave_bytes = self._build_wave_bytes(
                waveform, speech_settings.sample_rate_hz
            )
            await asyncio.to_thread(
                self._file_system.write_bytes, narration_path, wave_bytes
            )
            await self.video_editor.add_audio_track(
                target,
                narration_path,
                stream_title=speech_settings.track_title,
            )
        finally:
            await asyncio.to_thread(
                self._file_system.unlink, narration_path, missing_ok=True
            )

    @staticmethod
    def _build_wave_bytes(waveform: bytes, sample_rate: int) -> bytes:
        """WAVEデータをメモリ上で生成する。"""
        with io.BytesIO() as buffer:
            with wave.open(buffer, "wb") as wave_writer:
                wave_writer.setnchannels(1)
                wave_writer.setsampwidth(2)
                wave_writer.setframerate(sample_rate)
                wave_writer.writeframes(waveform)
            return buffer.getvalue()

    @staticmethod
    def _compose_wave(
        segments: List[Tuple[float, bytes]],
        sample_rate: int,
    ) -> bytes:
        """複数の音声セグメントを1つの波形に合成する。"""
        timeline: array[int] = array("h")
        for start_sec, audio_bytes in segments:
            samples: array[int] = array("h")
            samples.frombytes(audio_bytes)
            start_index = max(int(round(start_sec * sample_rate)), 0)
            SubtitleProcessor._mix_into_timeline(
                timeline, samples, start_index
            )
        return timeline.tobytes()

    @staticmethod
    def _mix_into_timeline(
        timeline: array[int],
        samples: array[int],
        start_index: int,
    ) -> None:
        """タイムラインに音声サンプルをミックスする。"""
        required_length = start_index + len(samples)
        if len(timeline) < required_length:
            timeline.extend([0] * (required_length - len(timeline)))
        for offset, sample in enumerate(samples):
            idx = start_index + offset
            mixed = timeline[idx] + sample
            if mixed > 32767:
                timeline[idx] = 32767
            elif mixed < -32768:
                timeline[idx] = -32768
            else:
                timeline[idx] = mixed

    @staticmethod
    def _parse_srt(srt_text: str) -> List[Tuple[float, float, str]]:
        """SRT テキストをパースして (開始秒, 終了秒, テキスト) のリストを返す。"""
        pattern = re.compile(
            r"(?P<start>\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(?P<end>\d{2}:\d{2}:\d{2},\d{3})",
        )
        entries: List[Tuple[float, float, str]] = []
        if not srt_text.strip():
            return entries
        blocks = re.split(r"\n{2,}", srt_text.strip())
        for block in blocks:
            lines = [
                line.strip() for line in block.splitlines() if line.strip()
            ]
            if not lines:
                continue
            first_line = lines[0]
            if first_line.isdigit():
                lines = lines[1:]
                if not lines:
                    continue
                first_line = lines[0]
            match = pattern.match(first_line)
            if not match:
                continue
            start = SubtitleProcessor._to_seconds(match.group("start"))
            end = SubtitleProcessor._to_seconds(match.group("end"))
            text_lines = lines[1:]
            text = "\n".join(text_lines)
            entries.append((start, end, text))
        return entries

    @staticmethod
    def _to_seconds(timestamp: str) -> float:
        """SRT タイムスタンプ (HH:MM:SS,mmm) を秒数に変換する。"""
        hour = int(timestamp[0:2])
        minute = int(timestamp[3:5])
        second = int(timestamp[6:8])
        millisecond = int(timestamp[9:12])
        return hour * 3600 + minute * 60 + second + millisecond / 1000
