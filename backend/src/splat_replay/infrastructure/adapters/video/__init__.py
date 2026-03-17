"""Video processing adapters."""

from __future__ import annotations

from splat_replay.infrastructure.adapters.video.adaptive_video_recorder import (
    AdaptiveVideoRecorder,
)
from splat_replay.infrastructure.adapters.video.ffmpeg_processor import (
    FFmpegProcessor,
)
from splat_replay.infrastructure.adapters.video.replay_recorder_controller import (
    ReplayRecorderController,
)
from splat_replay.infrastructure.adapters.video.recorder_with_transcription import (
    RecorderWithTranscription,
)

__all__ = [
    "AdaptiveVideoRecorder",
    "FFmpegProcessor",
    "ReplayRecorderController",
    "RecorderWithTranscription",
]
