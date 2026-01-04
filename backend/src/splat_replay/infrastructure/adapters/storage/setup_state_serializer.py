"""SetupState ↔ TOML辞書変換ロジック。

Clean Architectureの責務分離原則に基づき、
シリアライゼーション/デシリアライゼーションのみを担当する。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, cast

from structlog.stdlib import BoundLogger

from splat_replay.domain.models import SetupState, SetupStep
from splat_replay.infrastructure.logging import get_logger


class SetupStateSerializer:
    """SetupStateとTOML辞書形式の相互変換を担当。

    ファイルI/Oは行わず、純粋なデータ変換のみを担当する。
    これにより、テスタビリティと保守性が向上する。
    """

    def __init__(self, logger: BoundLogger | None = None) -> None:
        """シリアライザを初期化する。

        Args:
            logger: ログ出力用。Noneの場合はデフォルトロガーを使用
        """
        self._logger = logger or get_logger()

    def state_to_dict(self, state: SetupState) -> Dict[str, object]:
        """SetupStateをTOML辞書形式に変換する。

        Args:
            state: 変換するインストール状態

        Returns:
            TOML辞書形式のデータ（{"installer": {...}}）
        """
        installer_data: Dict[str, object] = {
            "is_completed": state.is_completed,
            "current_step": state.current_step.value,
            "completed_steps": [step.value for step in state.completed_steps],
            "skipped_steps": [step.value for step in state.skipped_steps],
            "step_details": state.step_details,
            "camera_permission_dialog_shown": state.camera_permission_dialog_shown,
            "youtube_permission_dialog_shown": state.youtube_permission_dialog_shown,
        }

        # installation_dateがNoneでない場合のみ追加（TOMLはNoneをサポートしないため）
        if state.installation_date is not None:
            installer_data["installation_date"] = (
                state.installation_date.isoformat()
            )

        return {"installer": installer_data}

    def dict_to_state(self, toml_data: Dict[str, object]) -> SetupState:
        """TOML辞書形式のデータをSetupStateに変換する。

        Args:
            toml_data: TOML辞書形式のデータ

        Returns:
            変換されたインストール状態

        Raises:
            ValueError: データ形式が不正な場合
        """
        # TOMLパース結果は動的型のためAnyを使用
        installer_data_raw = toml_data.get("installer", {})
        if not isinstance(installer_data_raw, dict):
            raise ValueError("installer data must be a mapping")
        installer_data: Dict[str, Any] = cast(
            Dict[str, Any], installer_data_raw
        )

        # 基本データの取得と変換
        is_completed = self._extract_bool(
            installer_data, "is_completed", False
        )
        current_step = self._extract_enum(
            installer_data,
            "current_step",
            SetupStep,
            SetupStep.HARDWARE_CHECK,
        )
        completed_steps = self._extract_enum_list(
            installer_data, "completed_steps", SetupStep
        )
        skipped_steps = self._extract_enum_list(
            installer_data, "skipped_steps", SetupStep
        )
        step_details = self._extract_dict(installer_data, "step_details")
        installation_date = self._extract_datetime(
            installer_data, "installation_date"
        )
        camera_permission_dialog_shown = self._extract_bool(
            installer_data, "camera_permission_dialog_shown", False
        )
        youtube_permission_dialog_shown = self._extract_bool(
            installer_data, "youtube_permission_dialog_shown", False
        )

        # SetupStateを作成
        return SetupState(
            is_completed=is_completed,
            current_step=current_step,
            completed_steps=tuple(completed_steps),
            skipped_steps=tuple(skipped_steps),
            step_details=step_details,
            installation_date=installation_date,
            camera_permission_dialog_shown=camera_permission_dialog_shown,
            youtube_permission_dialog_shown=youtube_permission_dialog_shown,
        )

    def _extract_bool(
        self, data: Dict[str, Any], key: str, default: bool
    ) -> bool:
        """辞書からbool値を安全に取り出す。

        Args:
            data: 辞書
            key: キー
            default: デフォルト値

        Returns:
            bool値
        """
        value = data.get(key, default)
        return bool(value) if value is not None else default

    def _extract_enum(
        self,
        data: Dict[str, Any],
        key: str,
        enum_type: type[SetupStep],
        default: SetupStep,
    ) -> SetupStep:
        """辞書からEnum値を安全に取り出す。

        Args:
            data: 辞書
            key: キー
            enum_type: Enum型
            default: デフォルト値

        Returns:
            Enum値
        """
        value = data.get(key, default.value)
        try:
            return enum_type(str(value))
        except ValueError:
            self._logger.warning(
                "Invalid enum value, using default",
                key=key,
                value=value,
                default=default.value,
            )
            return default

    def _extract_enum_list(
        self, data: Dict[str, Any], key: str, enum_type: type[SetupStep]
    ) -> list[SetupStep]:
        """辞書からEnum値のリストを安全に取り出す。

        Args:
            data: 辞書
            key: キー
            enum_type: Enum型

        Returns:
            Enum値のリスト（無効な値はスキップ）
        """
        raw_list = data.get(key, [])
        if not isinstance(raw_list, list):
            return []

        result = []
        for value in raw_list:
            try:
                result.append(enum_type(str(value)))
            except ValueError:
                self._logger.warning(
                    "Invalid enum list value, skipping",
                    key=key,
                    value=value,
                )
        return result

    def _extract_dict(self, data: Dict[str, Any], key: str) -> Dict[str, Any]:
        """辞書から辞書を安全に取り出す。

        Args:
            data: 辞書
            key: キー

        Returns:
            辞書（存在しない場合は空辞書）
        """
        value = data.get(key, {})
        return dict(value) if isinstance(value, dict) else {}

    def _extract_datetime(
        self, data: Dict[str, Any], key: str
    ) -> datetime | None:
        """辞書からdatetime値を安全に取り出す。

        Args:
            data: 辞書
            key: キー

        Returns:
            datetime値（存在しないかパース失敗の場合はNone）
        """
        value = data.get(key)
        if not value:
            return None

        try:
            return datetime.fromisoformat(str(value))
        except ValueError:
            self._logger.warning(
                "Invalid datetime format, ignoring",
                key=key,
                value=value,
            )
            return None
