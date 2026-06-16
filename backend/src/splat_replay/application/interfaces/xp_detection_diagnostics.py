from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from splat_replay.domain.models import Frame


@dataclass(frozen=True)
class XPDetectionDiagnosticsRecord:
    """XP 誤検知の原因断定に必要な1回分の観測データ。"""

    timestamp: datetime
    phase: str
    record_state: str
    match_select_detected: bool
    detected_game_mode: str | None
    detected_match: str | None
    matching_start_detected: bool
    ocr_text: str | None
    parsed_xp: float | None
    validation_error: str | None
    accepted_xp: str | None
    previous_rate: str | None
    previous_xp: float | None
    delta_from_previous_xp: float | None
    previous_candidate_xp: float | None
    delta_from_previous_candidate_xp: float | None
    same_candidate_count: int
    metadata_will_update: bool
    xp_roi: Frame
    xp_processed: Frame
    x_select_roi: Frame | None = None


class XPDetectionDiagnosticsPort(Protocol):
    """XP 検出診断を保存するポート。"""

    def is_enabled(self) -> bool: ...

    def record(self, record: XPDetectionDiagnosticsRecord) -> str | None: ...
