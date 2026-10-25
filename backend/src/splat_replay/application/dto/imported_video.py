"""持込動画のジョブと認識結果。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


ImportJobState = Literal[
    "queued",
    "scanning",
    "ready",
    "editing",
    "completed",
    "failed",
    "cancelled",
]


@dataclass(frozen=True)
class ImportedBattleDTO:
    id: str
    start_seconds: float
    end_seconds: float
    segments: tuple[tuple[float, float], ...]
    selected: bool
    metadata: dict[str, object]
    title: str | None = None
    description: str | None = None
    clip_ready: bool = False
    duration_seconds: float = 0.0
    has_thumbnail: bool = False
    has_subtitle: bool = False
    evidence_assets: dict[str, str] = field(default_factory=dict)
    evidence_seconds: dict[str, float] = field(default_factory=dict)
    evidence_regions: dict[str, dict[str, tuple[int, int, int, int]]] = field(
        default_factory=dict
    )
    evidence_sizes: dict[str, tuple[int, int]] = field(default_factory=dict)


@dataclass(frozen=True)
class ImportedVideoOutputDTO:
    id: str
    title: str
    description: str
    has_thumbnail: bool
    has_subtitle: bool
    candidate_ids: tuple[str, ...]


@dataclass(frozen=True)
class ImportedVideoJobDTO:
    id: str
    source_name: str
    source_suffix: str
    state: ImportJobState
    progress_percent: float
    duration_seconds: float | None
    has_audio: bool | None
    candidates: tuple[ImportedBattleDTO, ...]
    error: str | None
    title: str | None
    description: str | None
    created_at: str
    has_output: bool
    has_thumbnail: bool
    has_subtitle: bool
    output_id: str | None = None
    outputs: tuple[ImportedVideoOutputDTO, ...] = ()
    source_started_at: str | None = None
    source_started_at_inferred: bool = False
    output_directory: str | None = None


@dataclass(frozen=True)
class ImportedVideoInfo:
    duration_seconds: float
    has_video: bool
    has_audio: bool
