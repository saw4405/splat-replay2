"""設定保存ユースケース。"""

from __future__ import annotations

from pathlib import Path

from splat_replay.shared.config import AppSettings


class SaveSettingsUseCase:
    """設定をファイルへ書き出す。"""

    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings

    def execute(self, path: Path) -> None:
        """現在の設定を指定ファイルへ保存する。"""
        _ = path
        _ = self.settings
        # 実装は後で追加
