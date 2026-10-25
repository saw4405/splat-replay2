"""不要な手順の記録を汎用的に読み捨てる。"""

import json
from unittest.mock import MagicMock
import pytest
from splat_replay.domain.models import SetupStep
from splat_replay.infrastructure.adapters.storage.setup_state_serializer import (
    SetupStateSerializer,
)


@pytest.mark.parametrize("removed_step", ["font_installation", "removed_step"])
def test_removed_records_are_discarded_and_valid_progress_is_kept(
    removed_step: str,
) -> None:
    completed = [
        "hardware_check",
        "ffmpeg_setup",
        "obs_setup",
        "tesseract_setup",
    ]
    state = SetupStateSerializer(logger=MagicMock()).dict_to_state(
        {
            "installer": {
                "current_step": removed_step,
                "completed_steps": completed + [removed_step],
                "skipped_steps": [removed_step],
                "step_details": {
                    removed_step: {"old": True},
                    "tesseract_setup": {"tesseract-install": True},
                },
            }
        }
    )
    assert state.current_step is SetupStep.TRANSCRIPTION_SETUP
    assert [s.value for s in state.completed_steps] == completed
    assert state.skipped_steps == ()
    assert state.step_details == {
        "tesseract_setup": {"tesseract-install": True}
    }
    assert removed_step not in json.dumps(
        SetupStateSerializer(logger=MagicMock()).state_to_dict(state)
    )


def test_valid_current_step_is_preserved() -> None:
    state = SetupStateSerializer(logger=MagicMock()).dict_to_state(
        {"installer": {"current_step": "obs_setup"}}
    )
    assert state.current_step is SetupStep.OBS_SETUP
