"""廃止した手順を旧設定から読んでも再表示しない。"""

from splat_replay.domain.models import SetupStep
from splat_replay.infrastructure.adapters.storage.setup_state_serializer import (
    SetupStateSerializer,
)


def test_old_setup_state_skips_removed_step_and_keeps_saved_details() -> None:
    details = {"font_installation": {"font-place": True}}
    state = SetupStateSerializer().dict_to_state(
        {
            "installer": {
                "current_step": "font_installation",
                "completed_steps": ["font_installation"],
                "step_details": details,
            }
        }
    )
    assert state.current_step is SetupStep.TRANSCRIPTION_SETUP
    assert state.step_details == details
    assert state.get_progress_percentage() == 0
    assert SetupStep.FONT_INSTALLATION not in SetupStep.get_all_steps()
    assert (
        SetupStep.TESSERACT_SETUP.get_next_step()
        is SetupStep.TRANSCRIPTION_SETUP
    )
