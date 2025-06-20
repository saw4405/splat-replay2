from splat_replay.shared.di import configure_container
from splat_replay.application import (
    PauseRecordingUseCase,
    ResumeRecordingUseCase,
    DaemonUseCase,
)
from splat_replay.domain.services.state_machine import StateMachine
from splat_replay.shared.config import AppSettings, YouTubeSettings


def test_shared_state_machine() -> None:
    container = configure_container()
    pause = container.resolve(PauseRecordingUseCase)
    resume = container.resolve(ResumeRecordingUseCase)
    daemon = container.resolve(DaemonUseCase)

    assert isinstance(pause.sm, StateMachine)
    assert pause.sm is resume.sm
    assert pause.sm is daemon.sm


def test_settings_registered() -> None:
    container = configure_container()
    settings = container.resolve(AppSettings)
    yt = container.resolve(YouTubeSettings)
    assert yt is settings.youtube
