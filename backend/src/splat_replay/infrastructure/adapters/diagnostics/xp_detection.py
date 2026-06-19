from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from splat_replay.application.interfaces import LoggerPort
from splat_replay.application.interfaces.xp_detection_diagnostics import (
    XPDetectionDiagnosticsRecord,
)
from splat_replay.infrastructure.filesystem import paths

XP_DETECTION_DIAGNOSTICS_DIR = paths.OUTPUTS_DIR / "xp_detection_diagnostics"


class FileXPDetectionDiagnostics:
    """XP 検出診断を JSONL と ROI 画像として保存する。"""

    def __init__(
        self,
        root_dir: Path | None = None,
        logger: LoggerPort | None = None,
    ) -> None:
        self._root_dir = root_dir or XP_DETECTION_DIAGNOSTICS_DIR
        self._logger = logger
        self._session_dir: Path | None = None
        self._counter = 0

    def is_enabled(self) -> bool:
        return self._root_dir.is_dir()

    def record(self, record: XPDetectionDiagnosticsRecord) -> str | None:
        if not self.is_enabled():
            return None
        try:
            session_dir = self._ensure_session_dir()
            self._counter += 1
            prefix = f"{self._counter:06d}"
            xp_roi_path = session_dir / f"{prefix}_xp_roi.png"
            xp_processed_path = session_dir / f"{prefix}_xp_processed.png"
            x_select_roi_path = (
                session_dir / f"{prefix}_x_select_roi.png"
                if record.x_select_roi is not None
                else None
            )

            cv2.imwrite(str(xp_roi_path), record.xp_roi)
            cv2.imwrite(str(xp_processed_path), record.xp_processed)
            if (
                x_select_roi_path is not None
                and record.x_select_roi is not None
            ):
                cv2.imwrite(str(x_select_roi_path), record.x_select_roi)

            row = self._to_json_row(
                record=record,
                xp_roi_path=xp_roi_path,
                xp_processed_path=xp_processed_path,
                x_select_roi_path=x_select_roi_path,
            )
            with (session_dir / "events.jsonl").open(
                "a", encoding="utf-8"
            ) as handle:
                handle.write(json.dumps(row, ensure_ascii=False))
                handle.write("\n")
            return session_dir.resolve().as_posix()
        except Exception as exc:
            if self._logger is not None:
                self._logger.warning(
                    "XP 検出診断のファイル保存に失敗しました",
                    error=str(exc),
                )
            return None

    def _ensure_session_dir(self) -> Path:
        if self._session_dir is not None:
            return self._session_dir

        base_name = datetime.now().strftime("%Y%m%d_%H%M%S")
        session_dir = self._root_dir / base_name
        suffix = 2
        while session_dir.exists():
            session_dir = self._root_dir / f"{base_name}_{suffix}"
            suffix += 1
        session_dir.mkdir(parents=False, exist_ok=False)
        self._session_dir = session_dir
        return session_dir

    def _to_json_row(
        self,
        *,
        record: XPDetectionDiagnosticsRecord,
        xp_roi_path: Path,
        xp_processed_path: Path,
        x_select_roi_path: Path | None,
    ) -> dict[str, Any]:
        row: dict[str, Any] = {
            "timestamp": record.timestamp.isoformat(),
            "phase": record.phase,
            "record_state": record.record_state,
            "match_select_detected": record.match_select_detected,
            "detected_game_mode": record.detected_game_mode,
            "detected_match": record.detected_match,
            "matching_start_detected": record.matching_start_detected,
            "ocr_text": record.ocr_text,
            "parsed_xp": record.parsed_xp,
            "validation_error": record.validation_error,
            "accepted_xp": record.accepted_xp,
            "previous_rate": record.previous_rate,
            "previous_xp": record.previous_xp,
            "delta_from_previous_xp": record.delta_from_previous_xp,
            "previous_candidate_xp": record.previous_candidate_xp,
            "delta_from_previous_candidate_xp": (
                record.delta_from_previous_candidate_xp
            ),
            "same_candidate_count": record.same_candidate_count,
            "metadata_will_update": record.metadata_will_update,
            "xp_processed_connected_component_count": (
                record.xp_processed_connected_component_count
            ),
            "xp_roi_image": xp_roi_path.resolve().as_posix(),
            "xp_processed_image": xp_processed_path.resolve().as_posix(),
            "x_select_roi_image": (
                x_select_roi_path.resolve().as_posix()
                if x_select_roi_path is not None
                else None
            ),
        }
        row.update(_gray_stats("xp_roi", record.xp_roi))
        row.update(_gray_stats("xp_processed", record.xp_processed))
        if record.x_select_roi is not None:
            row.update(_hsv_stats("x_select_roi", record.x_select_roi))
            row.update(_x_battle_select_color_stats(record.x_select_roi))
        return row


def _gray_stats(prefix: str, image: np.ndarray) -> dict[str, Any]:
    if image.ndim == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image
    return {
        f"{prefix}_gray_min": int(gray.min()),
        f"{prefix}_gray_max": int(gray.max()),
        f"{prefix}_gray_mean": float(gray.mean()),
        f"{prefix}_gray_std": float(gray.std()),
    }


def _hsv_stats(prefix: str, image: np.ndarray) -> dict[str, Any]:
    if image.ndim != 3:
        return {}
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    return {
        f"{prefix}_hsv_min": [
            int(hsv[:, :, channel].min()) for channel in range(3)
        ],
        f"{prefix}_hsv_max": [
            int(hsv[:, :, channel].max()) for channel in range(3)
        ],
        f"{prefix}_hsv_mean": [
            float(hsv[:, :, channel].mean()) for channel in range(3)
        ],
        f"{prefix}_hsv_std": [
            float(hsv[:, :, channel].std()) for channel in range(3)
        ],
    }


def _x_battle_select_color_stats(image: np.ndarray) -> dict[str, Any]:
    if image.ndim != 3:
        return {}
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    lower = np.array([80, 230, 230], dtype=np.uint8)
    upper = np.array([90, 255, 255], dtype=np.uint8)
    mask = cv2.inRange(hsv, lower, upper)
    return {
        "x_select_x_battle_hsv_lower": lower.tolist(),
        "x_select_x_battle_hsv_upper": upper.tolist(),
        "x_select_x_battle_hsv_match_ratio": (
            float(np.count_nonzero(mask)) / float(mask.size)
            if mask.size
            else 0.0
        ),
        "x_select_x_battle_hsv_threshold": 0.9,
    }
