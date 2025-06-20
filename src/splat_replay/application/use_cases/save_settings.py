"""設定保存ユースケース。"""

from __future__ import annotations

from pathlib import Path

from splat_replay.shared.config import AppSettings
from splat_replay.shared.logger import get_logger


class SaveSettingsUseCase:
    """設定をファイルへ書き出す。"""

    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings
        self.logger = get_logger()

    def execute(self, path: Path) -> None:
        """現在の設定を指定ファイルへ保存する。"""
        self.logger.info("設定保存", path=str(path))
        _ = path
        _ = self.settings
        # 実装は後で追加
