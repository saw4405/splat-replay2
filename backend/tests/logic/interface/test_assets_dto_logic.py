from __future__ import annotations

import sys
from pathlib import Path
import pytest
from pydantic import ValidationError as PydanticValidationError

# ``src`` ディレクトリを ``sys.path`` へ追加
BASE = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(BASE / "src"))

from splat_replay.interface.web.routers.recording import (
    RecordingMetadataUpdateRequest,
)
from splat_replay.interface.web.schemas.metadata import MetadataUpdateRequest


@pytest.mark.parametrize(
    "payload",
    [
        {"gold_medals": -1},
        {"silver_medals": 4},
        {"gold_medals": 2, "silver_medals": 2},
    ],
)
def test_metadata_update_request_rejects_invalid_medal_counts(
    payload: dict[str, int],
) -> None:
    """MetadataUpdateRequest が不正なメダル数でバリデーションエラーを起こすことを検証。"""
    with pytest.raises(PydanticValidationError):
        MetadataUpdateRequest.parse_obj(payload)


@pytest.mark.parametrize(
    "payload",
    [
        {"gold_medals": -1},
        {"silver_medals": 4},
        {"gold_medals": 2, "silver_medals": 2},
    ],
)
def test_recording_metadata_update_request_rejects_invalid_medal_counts(
    payload: dict[str, int],
) -> None:
    """RecordingMetadataUpdateRequest が不正なメダル数でバリデーションエラーを起こすことを検証。"""
    with pytest.raises(PydanticValidationError):
        RecordingMetadataUpdateRequest.parse_obj(payload)
