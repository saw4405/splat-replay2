"""システムチェックサービス。"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Optional

from structlog.stdlib import BoundLogger

from splat_replay.application.interfaces import (
    CommandExecutionError,
    SystemCommandPort,
)


class SoftwareCheckResult:
    """ソフトウェアチェック結果。"""

    def __init__(
        self,
        is_installed: bool,
        version: Optional[str] = None,
        installation_path: Optional[Path] = None,
        error_message: Optional[str] = None,
    ) -> None:
        """チェック結果を初期化する。

        Args:
            is_installed: インストールされているかどうか
            version: バージョン情報（取得できた場合）
            installation_path: インストールパス（取得できた場合）
            error_message: エラーメッセージ（エラーが発生した場合）
        """
        self.is_installed = is_installed
        self.version = version
        self.installation_path = installation_path
        self.error_message = error_message


class SystemCheckService:
    """システム上のソフトウェアインストール状態を確認するサービス。"""

    def __init__(
        self,
        command_port: SystemCommandPort,
        logger: BoundLogger,
    ) -> None:
        """サービスを初期化する。

        Args:
            command_port: システムコマンド実行ポート
            logger: ロガー
        """
        self._command_port = command_port
        self._logger = logger

    def check_obs_installation(self) -> SoftwareCheckResult:
        """OBSのインストール状態を確認する。

        Returns:
            OBSのチェック結果
        """
        self._logger.info("Checking OBS installation")

        # OBSの実行ファイルパスを確認
        common_paths = [
            Path("C:/Program Files/obs-studio/bin/64bit/obs64.exe"),
            Path("C:/Program Files (x86)/obs-studio/bin/64bit/obs64.exe"),
        ]

        for path in common_paths:
            if path.exists():
                self._logger.info("OBS found", path=str(path))
                # バージョン情報を取得
                version = self._get_obs_version(path)
                return SoftwareCheckResult(
                    is_installed=True,
                    version=version,
                    installation_path=path,
                )

        self._logger.info("OBS not found")
        return SoftwareCheckResult(
            is_installed=False,
            error_message="OBS Studio が見つかりませんでした",
        )

    def check_ffmpeg_installation(self) -> SoftwareCheckResult:
        """FFMPEGのインストール状態を確認する。

        Returns:
            FFMPEGのチェック結果
        """
        self._logger.info("Checking FFMPEG installation")

        # ffmpegコマンドが実行可能かチェック
        if not self._command_port.check_command_exists("ffmpeg"):
            self._logger.info("FFMPEG command not found")
            return SoftwareCheckResult(
                is_installed=False,
                error_message="FFMPEG が見つかりませんでした",
            )

        # バージョン情報を取得
        try:
            result = self._command_port.execute_command(
                ["ffmpeg", "-version"],
                timeout=5.0,
            )

            if result.success:
                version = self._extract_ffmpeg_version(result.stdout)
                self._logger.info("FFMPEG found", version=version)
                return SoftwareCheckResult(
                    is_installed=True,
                    version=version,
                )
            else:
                self._logger.warning(
                    "FFMPEG version check failed",
                    stderr=result.stderr,
                )
                return SoftwareCheckResult(
                    is_installed=False,
                    error_message="FFMPEG のバージョン確認に失敗しました",
                )

        except CommandExecutionError as e:
            self._logger.error(
                "FFMPEG version check error",
                error=str(e),
            )
            return SoftwareCheckResult(
                is_installed=False,
                error_message=f"FFMPEG の確認中にエラーが発生しました: {e}",
            )

    def check_tesseract_installation(self) -> SoftwareCheckResult:
        """Tesseractのインストール状態を確認する。

        1. まずtesseractコマンドが実行可能かを確認
        2. 実行できない場合、C:\\Program Files\\Tesseract-OCR\\tesseract.exeが存在するかを確認
        3. ファイルがあればインストール済として返す

        Returns:
            Tesseractのチェック結果
        """
        self._logger.info("Checking Tesseract installation")

        # 1. まずtesseractコマンドが実行可能かを確認
        if self._command_port.check_command_exists("tesseract"):
            # バージョン情報を取得
            try:
                result = self._command_port.execute_command(
                    ["tesseract", "--version"],
                    timeout=5.0,
                )

                if result.success:
                    version = self._extract_tesseract_version(result.stdout)
                    self._logger.info(
                        "Tesseract found via command", version=version
                    )
                    return SoftwareCheckResult(
                        is_installed=True,
                        version=version,
                    )
            except CommandExecutionError as e:
                self._logger.warning(
                    "Tesseract command exists but version check failed",
                    error=str(e),
                )

        # 2. C:\Program Files\Tesseract-OCR\tesseract.exeが存在するかを確認
        tesseract_exe = Path("C:/Program Files/Tesseract-OCR/tesseract.exe")

        if tesseract_exe.exists():
            self._logger.info(
                "Tesseract executable found", path=str(tesseract_exe)
            )
            # ファイルが存在すればインストール済とみなす
            return SoftwareCheckResult(
                is_installed=True,
                version="Installed",
                installation_path=tesseract_exe,
            )

        # 3. どちらも見つからない場合
        self._logger.info("Tesseract not found")
        return SoftwareCheckResult(
            is_installed=False,
            error_message="Tesseract が見つかりませんでした",
        )

    def check_environment_variable(self, var_name: str) -> bool:
        """環境変数が設定されているかどうかを確認する。

        Args:
            var_name: 確認する環境変数名

        Returns:
            環境変数が設定されている場合はTrue、そうでなければFalse
        """
        value = os.environ.get(var_name)
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
        exists = path.exists() and path.is_file()

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
        from splat_replay.shared.paths import THUMBNAIL_ASSETS_DIR

        self._logger.info("Checking font installation", font_name=font_name)

        try:
            # サムネイル用アセットディレクトリ (assets/thumbnail) を使用
            font_dir = THUMBNAIL_ASSETS_DIR
            self._logger.info(
                "Checking font directory", font_dir=str(font_dir)
            )

            # ikamodoki1.ttf ファイルをチェック
            font_path = font_dir / f"{font_name}.ttf"
            if font_path.exists() and font_path.is_file():
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
        from splat_replay.shared.paths import CONFIG_DIR

        self._logger.info("Checking YouTube credentials")

        try:
            # configフォルダ内のclient_secrets.jsonを確認
            credentials_path = CONFIG_DIR / "client_secrets.json"
            self._logger.info(
                "Checking credentials path", path=str(credentials_path)
            )

            if credentials_path.exists() and credentials_path.is_file():
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
            if path.exists() and path.is_dir():
                # Processing.NDI.Lib.x64.dll の存在を確認
                dll_path = path / "Processing.NDI.Lib.x64.dll"
                if dll_path.exists():
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

    def _get_obs_version(self, obs_path: Path) -> Optional[str]:
        """OBSのバージョン情報を取得する。

        Args:
            obs_path: OBSの実行ファイルパス

        Returns:
            バージョン情報（取得できない場合はNone）
        """
        try:
            # OBSのバージョン情報はファイルプロパティから取得する必要がある
            # ここでは簡易的にNoneを返す（実装は後で拡張可能）
            return None
        except Exception as e:
            self._logger.warning(
                "Failed to get OBS version",
                error=str(e),
            )
            return None

    def _extract_ffmpeg_version(self, output: str) -> Optional[str]:
        """FFMPEGの出力からバージョン情報を抽出する。

        Args:
            output: ffmpeg -versionの出力

        Returns:
            バージョン情報（抽出できない場合はNone）
        """
        # "ffmpeg version X.Y.Z" のパターンを探す
        match = re.search(r"ffmpeg version ([^\s]+)", output)
        if match:
            return match.group(1)
        return None

    def _extract_tesseract_version(self, output: str) -> Optional[str]:
        """Tesseractの出力からバージョン情報を抽出する。

        Args:
            output: tesseract --versionの出力

        Returns:
            バージョン情報（抽出できない場合はNone）
        """
        # "tesseract X.Y.Z" のパターンを探す
        match = re.search(r"tesseract ([^\s]+)", output)
        if match:
            return match.group(1)
        return None
