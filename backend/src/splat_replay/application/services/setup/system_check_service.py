"""システムチェックサービス。

Phase 9 リファクタリング:
- SoftwareCheckResult を frozen dataclass 化（Phase 8 の不変性方針に準拠）

Phase 10 リファクタリング:
- Strategy パターンで個別チェッカーに分割
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from splat_replay.application.interfaces.common import (
    FileSystemPort,
    LoggerPort,
    PathsPort,
)
from splat_replay.application.interfaces.system import EnvironmentPort
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
        paths: PathsPort,
        file_system: FileSystemPort,
        environment: EnvironmentPort,
        logger: LoggerPort,
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
        self._paths = paths
        self._file_system = file_system
        self._environment = environment
        self._logger = logger

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
            # サムネイル用アセットディレクトリ (assets/thumbnail) を使用
            font_dir = self._paths.get_thumbnail_assets_dir()
            self._logger.info(
                "Checking font directory", font_dir=str(font_dir)
            )

            # ikamodoki1.ttf ファイルをチェック
            font_path = font_dir / f"{font_name}.ttf"
            if self._file_system.is_file(font_path):
                self._logger.info("Font found", path=str(font_path))
                return SoftwareCheckResult(
                    is_installed=True,
                    installation_path=font_path,
                )

            self._logger.info(
                "Font not found", font_name=font_name, font_dir=str(font_dir)
            )
            return SoftwareCheckResult(
                is_installed=False,
                error_message=f"{font_name}.ttf フォントが見つかりませんでした",
            )
        except Exception as e:
            self._logger.error("Font check error", error=str(e))
            return SoftwareCheckResult(
                is_installed=False,
                error_message=f"フォント確認中にエラーが発生しました: {e}",
            )

    def check_youtube_credentials(self) -> SoftwareCheckResult:
        """YouTube API 認証情報の存在を確認する。

        Returns:
            認証情報のチェック結果
        """
        self._logger.info("Checking YouTube credentials")

        try:
            # configフォルダ内のclient_secret.jsonを確認
            config_dir = self._paths.get_config_dir()
            credentials_path = config_dir / "client_secret.json"
            self._logger.info(
                "Checking credentials path", path=str(credentials_path)
            )

            if self._file_system.is_file(credentials_path):
                self._logger.info(
                    "YouTube credentials found", path=str(credentials_path)
                )
                return SoftwareCheckResult(
                    is_installed=True,
                    installation_path=credentials_path,
                )

            self._logger.info("YouTube credentials not found")
            return SoftwareCheckResult(
                is_installed=False,
                error_message="YouTube API 認証情報ファイルが見つかりませんでした",
            )
        except Exception as e:
            self._logger.error("YouTube credentials check error", error=str(e))
            return SoftwareCheckResult(
                is_installed=False,
                error_message=f"認証情報確認中にエラーが発生しました: {e}",
            )

    def check_ndi_runtime_installation(self) -> SoftwareCheckResult:
        """NDI Runtimeのインストール状態を確認する。

        Returns:
            NDI Runtimeのチェック結果
        """
        self._logger.info("Checking NDI Runtime installation")

        # NDI Runtimeの一般的なインストールパスをチェック
        common_paths = [
            Path("C:/Program Files/NDI/NDI 6 Runtime/v6"),
            Path("C:/Program Files/NDI/NDI 5 Runtime/v5"),
            Path("C:/Program Files (x86)/NDI/NDI 6 Runtime/v6"),
            Path("C:/Program Files (x86)/NDI/NDI 5 Runtime/v5"),
        ]

        for path in common_paths:
            if self._file_system.is_dir(path):
                # Processing.NDI.Lib.x64.dll の存在を確認
                dll_path = path / "Processing.NDI.Lib.x64.dll"
                if self._file_system.exists(dll_path):
                    self._logger.info("NDI Runtime found", path=str(path))
                    # バージョン情報をパスから抽出
                    version = None
                    if "NDI 6" in str(path):
                        version = "6.x"
                    elif "NDI 5" in str(path):
                        version = "5.x"

                    return SoftwareCheckResult(
                        is_installed=True,
                        version=version,
                        installation_path=path,
                    )

        self._logger.info("NDI Runtime not found")
        return SoftwareCheckResult(
            is_installed=False,
            error_message="NDI Runtime が見つかりませんでした",
        )
