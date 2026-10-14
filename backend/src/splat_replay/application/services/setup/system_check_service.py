"""システムチェックサービス。

Phase 9 リファクタリング:
- SoftwareCheckResult を frozen dataclass 化（Phase 8 の不変性方針に準拠）

Phase 10 リファクタリング:
- Strategy パターンで個別チェッカーに分割
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from splat_replay.application.interfaces.common import (
    FileSystemPort,
    LoggerPort,
    PathsPort,
)
from splat_replay.application.interfaces.thumbnail_font import (
    ThumbnailFontResolverPort,
)
from splat_replay.application.interfaces.system import EnvironmentPort
from splat_replay.application.interfaces.system import (
    OBSMainOutputCheckResult,
    OBSConfigurationCheckerPort,
    OBSWebSocketCheckResult,
)
from splat_replay.application.services.system.software_checker import (
    SoftwareChecker,
)


@dataclass(frozen=True)
class SoftwareCheckResult:
    """ソフトウェアチェック結果（不変）。

    Attributes:
        is_installed: インストールされているかどうか
        version: バージョン情報（取得できた場合）
        installation_path: インストールパス（取得できた場合）
        error_message: エラーメッセージ（エラーが発生した場合）
    """

    is_installed: bool
    version: Optional[str] = None
    installation_path: Optional[Path] = None
    error_message: Optional[str] = None


class SystemCheckService:
    """システム上のソフトウェアインストール状態を確認するサービス。

    責務:
    - 各種チェッカーの統合
    - 環境変数・ファイル存在チェック
    - フォント・認証情報・NDI Runtimeのチェック
    """

    def __init__(
        self,
        obs_checker: SoftwareChecker,
        ffmpeg_checker: SoftwareChecker,
        tesseract_checker: SoftwareChecker,
        flac_checker: SoftwareChecker,
        ndi_checker: SoftwareChecker,
        font_resolver: ThumbnailFontResolverPort,
        paths: PathsPort,
        file_system: FileSystemPort,
        environment: EnvironmentPort,
        logger: LoggerPort,
        distroav_checker: SoftwareChecker,
        obs_configuration_checker: OBSConfigurationCheckerPort,
    ) -> None:
        """サービスを初期化する。

        Args:
            obs_checker: OBSチェッカー
            ffmpeg_checker: FFMPEGチェッカー
            tesseract_checker: Tesseractチェッカー
            paths: パス解決ポート
            logger: ロガーポート
        """
        self._obs_checker = obs_checker
        self._ffmpeg_checker = ffmpeg_checker
        self._tesseract_checker = tesseract_checker
        self._flac_checker = flac_checker
        self._ndi_checker = ndi_checker
        self._font_resolver = font_resolver
        self._paths = paths
        self._file_system = file_system
        self._environment = environment
        self._logger = logger
        self._distroav_checker = distroav_checker
        self._obs_configuration_checker = obs_configuration_checker

    def check_obs_main_output(self) -> OBSMainOutputCheckResult:
        """OBS の保存済み NDI Main Output を確認する。"""
        return self._obs_configuration_checker.check()

    def check_obs_websocket_configuration(
        self, host: str, port: int, password: str
    ) -> OBSWebSocketCheckResult:
        """OBS WebSocket の保存値を確認する。秘密値は結果に含めない。"""
        return self._obs_configuration_checker.check_websocket(
            host, port, password
        )

    def check_obs_installation(self) -> SoftwareCheckResult:
        """OBSのインストール状態を確認する。

        Returns:
            OBSのチェック結果
        """
        return self._obs_checker.check()

    def check_ffmpeg_installation(self) -> SoftwareCheckResult:
        """FFMPEGのインストール状態を確認する。

        Returns:
            FFMPEGのチェック結果
        """
        return self._ffmpeg_checker.check()

    def check_tesseract_installation(self) -> SoftwareCheckResult:
        """Tesseractのインストール状態を確認する。

        Returns:
            Tesseractのチェック結果
        """
        return self._tesseract_checker.check()

    def check_flac_installation(self) -> SoftwareCheckResult:
        """PATH から FLAC を実行できるか確認する。"""
        return self._flac_checker.check()

    @staticmethod
    def is_flac_required_for_transcription() -> bool:
        """現在の実装で字幕音声変換にFLACが必要なOSかを返す。"""
        return sys.platform == "darwin"

    def check_environment_variable(self, var_name: str) -> bool:
        """環境変数が設定されているかどうかを確認する。

        Args:
            var_name: 確認する環境変数名

        Returns:
            環境変数が設定されている場合はTrue、そうでなければFalse
        """
        value = self._environment.get(var_name)
        is_set = value is not None and value != ""

        self._logger.info(
            "Environment variable check",
            var_name=var_name,
            is_set=is_set,
        )

        return is_set

    def check_file_exists(self, path: Path) -> bool:
        """ファイルが存在するかどうかを確認する。

        Args:
            path: 確認するファイルパス

        Returns:
            ファイルが存在する場合はTrue、そうでなければFalse
        """
        exists = self._file_system.is_file(path)

        self._logger.info(
            "File existence check",
            path=str(path),
            exists=exists,
        )

        return exists

    def check_font_installation(
        self, font_name: str = "ikamodoki1"
    ) -> SoftwareCheckResult:
        """フォントのインストール状態を確認する。

        Args:
            font_name: 確認するフォント名（拡張子なし）

        Returns:
            フォントのチェック結果
        """
        self._logger.info("Checking font installation", font_name=font_name)

        try:
            font_path = self._paths.get_thumbnail_asset(f"{font_name}.ttf")
            resolved_path = self._font_resolver.resolve(font_path)
            if resolved_path is not None:
                self._logger.info("Font found", path=str(resolved_path))
                return SoftwareCheckResult(
                    is_installed=True,
                    installation_path=resolved_path,
                )

            self._logger.info(
                "Font not found", font_name=font_name, font_path=str(font_path)
            )
            return SoftwareCheckResult(
                is_installed=False,
                error_message=(
                    f"{font_name}.ttf と OS 標準の日本語フォントが見つかりませんでした"
                ),
            )
        except Exception as e:
            self._logger.error("Font check error", error=str(e))
            return SoftwareCheckResult(
                is_installed=False,
                error_message=f"フォント確認中にエラーが発生しました: {e}",
            )

    def check_youtube_credentials(self) -> SoftwareCheckResult:
        """YouTube OAuth client JSON を読み、必要な項目を検証する。

        Returns:
            認証情報のチェック結果
        """
        self._logger.info("Checking YouTube credentials")
        try:
            credentials_path = (
                self._paths.get_config_dir() / "client_secret.json"
            )
            if not self._file_system.is_file(credentials_path):
                return self._missing_youtube_credentials()

            parsed: object = json.loads(
                self._file_system.read_bytes(credentials_path).decode("utf-8")
            )
            if not isinstance(parsed, dict):
                return self._missing_youtube_credentials()

            client_config: object = parsed.get("installed") or parsed.get(
                "web"
            )
            if not isinstance(client_config, dict):
                return self._missing_youtube_credentials()

            required_values = (
                client_config.get("client_id"),
                client_config.get("client_secret"),
                client_config.get("auth_uri"),
                client_config.get("token_uri"),
            )
            if not all(
                isinstance(value, str) and bool(value.strip())
                for value in required_values
            ):
                return self._missing_youtube_credentials()

            self._logger.info("YouTube credentials are readable and valid")
            return SoftwareCheckResult(is_installed=True)
        except Exception as exc:  # noqa: BLE001
            self._logger.warning(
                "YouTube credentials could not be read or validated",
                error_type=type(exc).__name__,
            )
            return SoftwareCheckResult(
                is_installed=False,
                error_message=(
                    "YouTube API 認証情報ファイルを読み取れないか、"
                    "形式が正しくありません"
                ),
            )

    @staticmethod
    def _missing_youtube_credentials() -> SoftwareCheckResult:
        return SoftwareCheckResult(
            is_installed=False,
            error_message=(
                "有効な YouTube OAuth client_secret.json が見つかりませんでした"
            ),
        )

    def check_ndi_runtime_installation(self) -> SoftwareCheckResult:
        """NDI Runtimeのインストール状態を確認する。

        Returns:
            NDI Runtimeのチェック結果
        """
        self._logger.info("Checking NDI Runtime installation")
        return self._ndi_checker.check()

    def check_distroav_installation(self) -> SoftwareCheckResult:
        """OBSを起動せず、NDIプラグイン実行ファイルを確認する。"""
        return self._distroav_checker.check()
