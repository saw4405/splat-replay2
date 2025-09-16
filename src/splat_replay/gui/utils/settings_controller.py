"""
GUI 用設定管理コントローラー

設定の読み込み、保存、バックアップ・復元機能を提供
"""

from pathlib import Path
from typing import Dict, List, Union

from pydantic import SecretStr

from splat_replay.shared.config.app import SECTION_CLASSES, AppSettings

SettingItemType = Union[str, int, float, bool, Path, SecretStr, List[str]]


class GUISettingsController:
    """GUI 用設定管理コントローラー"""

    def __init__(self):
        """
        コントローラーを初期化する
        """
        self.original_settings = AppSettings.load_from_toml()
        self.editing_settings = self.original_settings.copy(deep=True)

        # {
        #     section_id: {
        #         "display": "セクション表示名",
        #         "fields": {
        #             field_id: {
        #                 "label": "表示名",
        #                 "help": "詳細説明",
        #                 "type": "UIタイプ",
        #                 "choices": ["選択肢1", "選択肢2", ...] | None,
        #                 "default": 値,
        #                 "recommended": True/False
        #             }, ...
        #         }
        #     }, ...
        # }
        self.setting_structure = AppSettings.get_setting_structure()

    def get_all_sections(self) -> Dict[str, str]:
        """
        すべてのセクション名とその表示名を取得

        Returns:
            セクション名と表示名の辞書
        """
        return {
            section_id: section_info["display"]
            for section_id, section_info in self.setting_structure.items()
        }

    def get_section_data(
        self, section_id: str
    ) -> Dict[str, Dict[str, SettingItemType]]:
        """
        指定されたセクションのフィールド情報を取得

        Args:
            section_id: セクションID

        Returns:
            fields情報の辞書

        Raises:
            AttributeError: 存在しないセクションIDが指定された場合
        """
        editing_settings_dict = self.editing_settings.dict()
        if (
            section_id not in self.setting_structure
            or section_id not in editing_settings_dict
        ):
            raise AttributeError(f"Unknown section: {section_id}")

        section_dict = editing_settings_dict[section_id]
        data = self.setting_structure[section_id]["fields"]
        for field_id, field_info in data.items():
            field_info["value"] = section_dict[field_id]
        return data

    def get_type(self, section_id: str, field_id: str) -> str:
        """
        指定されたセクションのフィールドの型を取得

        Args:
            section_id: セクションID
            field_id: フィールドID

        Returns:
            フィールドの型

        Raises:
            AttributeError: 存在しないセクションIDまたはフィールドIDが指定された場合
        """
        try:
            return self.setting_structure[section_id]["fields"][field_id][
                "type"
            ]
        except KeyError:
            raise AttributeError(
                f"Unknown section or field: {section_id}.{field_id}"
            )

    def update_section_data(
        self, section_name: str, data: Dict[str, SettingItemType]
    ) -> None:
        """
        セクションデータを更新

        Args:
            section_name: セクション名
            data: 更新するデータ

        Raises:
            AttributeError: 存在しないセクション名が指定された場合
        """
        if not hasattr(self.original_settings, section_name):
            raise AttributeError(f"Unknown section: {section_name}")

        section_class = self._get_section_class(section_name)
        updated_section = section_class(**data)
        setattr(self.editing_settings, section_name, updated_section)

    def save(self) -> None:
        """
        設定を TOML ファイルに保存

        Raises:
            IOError: ファイル保存に失敗した場合
        """
        try:
            self.editing_settings.save_to_toml()
        except Exception as e:
            raise IOError(f"設定ファイルの保存に失敗しました: {e}") from e

    def has_changes(self) -> bool:
        """
        設定に変更があるかどうかを確認

        Returns:
            変更がある場合 True
        """
        return self.editing_settings != self.original_settings

    def _get_section_class(self, section_name: str) -> type:
        if section_name not in SECTION_CLASSES:
            raise AttributeError(f"Unknown section: {section_name}")

        return SECTION_CLASSES[section_name]
