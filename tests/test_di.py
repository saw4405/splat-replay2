from splat_replay.shared.di import configure_container
from splat_replay.application import (
    PauseRecordingUseCase,
    ResumeRecordingUseCase,
    InitializeEnvironmentUseCase,
    DaemonUseCase,
)
from splat_replay.domain.services.state_machine import StateMachine
from splat_replay.shared.config import (
    AppSettings,
    YouTubeSettings,
    ImageMatchingSettings,
)
from splat_replay.infrastructure import (
    AnalyzerPlugin,
    SplatoonSalmonAnalyzer,
    FrameAnalyzer,
)
from pathlib import Path
import numpy as np


def test_shared_state_machine() -> None:
    container = configure_container()
    pause = container.resolve(PauseRecordingUseCase)
    resume = container.resolve(ResumeRecordingUseCase)
    init = container.resolve(InitializeEnvironmentUseCase)
    daemon = container.resolve(DaemonUseCase)

    assert isinstance(pause.sm, StateMachine)
    assert pause.sm is resume.sm
    assert pause.sm is daemon.sm
    assert pause.sm is init.sm


def test_settings_registered() -> None:
    container = configure_container()
    settings = container.resolve(AppSettings)
    yt = container.resolve(YouTubeSettings)
    assert yt is settings.youtube


def test_plugin_selection(monkeypatch):
    settings_path = Path("config/settings.toml")
    settings_path.write_text('game_mode = "salmon"')
    try:
        container = configure_container()
        plugin = container.resolve(AnalyzerPlugin)
        assert isinstance(plugin, SplatoonSalmonAnalyzer)
    finally:
        settings_path.unlink()


class DummyPlugin:
    def __init__(self) -> None:
        self.called = []

    def detect_battle_start(self, frame: np.ndarray) -> bool:
        self.called.append("start")
        return True

    def detect_loading(self, frame: np.ndarray) -> bool:
        self.called.append("load")
        return False

    def detect_loading_end(self, frame: np.ndarray) -> bool:
        self.called.append("end")
        return False

    def detect_result(self, frame: np.ndarray) -> bool:
        self.called.append("result")
        return False


def test_frame_analyzer_delegates() -> None:
    plugin = DummyPlugin()
    analyzer = FrameAnalyzer(plugin, ImageMatchingSettings())
    frame = np.zeros((1, 1, 3), dtype=np.uint8)
    assert analyzer.detect_battle_start(frame)
    assert plugin.called == ["start"]
