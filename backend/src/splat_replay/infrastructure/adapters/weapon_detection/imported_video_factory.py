"""持込動画のために通常録画と独立したブキ認識器を生成する。"""

from __future__ import annotations

from splat_replay.application.interfaces import (
    LoggerPort,
    WeaponRecognitionPort,
)
from splat_replay.application.interfaces.imported_video import (
    ImportedVideoWeaponRecognitionFactoryPort,
)
from splat_replay.domain.config import ImageMatchingSettings
from splat_replay.infrastructure.adapters.weapon_detection.recognizer import (
    WeaponRecognitionAdapter,
)
from splat_replay.infrastructure.adapters.weapon_detection.replay_recognizer import (
    ReplayWeaponRecognitionAdapter,
)
from splat_replay.infrastructure.di.runtime_profile import RuntimeProfile


class ImportedVideoWeaponRecognitionFactory(
    ImportedVideoWeaponRecognitionFactoryPort
):
    """持込ジョブごとに認識器を分け、取消し状態を共有しない。"""

    def __init__(
        self,
        profile: RuntimeProfile,
        settings: ImageMatchingSettings,
        logger: LoggerPort,
    ) -> None:
        self._profile = profile
        self._settings = settings
        self._logger = logger

    def create(self) -> WeaponRecognitionPort:
        if self._profile is RuntimeProfile.REPLAY:
            return ReplayWeaponRecognitionAdapter()
        return WeaponRecognitionAdapter(self._settings, self._logger)
