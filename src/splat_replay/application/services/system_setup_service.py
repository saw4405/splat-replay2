"""システムセットアップサービス。"""

from __future__ import annotations

import os
from pathlib import Path

from structlog.stdlib import BoundLogger

from splat_replay.application.interfaces import (
    CommandExecutionError,
    SystemCommandPort,
)
from splat_replay.application.services.system_check_service import SoftwareCheckResult


class SystemSetupService:
    """システムの設定変更を行うサービス。"""

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

    def setup_ffmpeg(self) -> SoftwareCheckResult:
        """FFMPEGのセットアップを行う。
        
        1. まずffmpegコマンドが実行可能かを確認
        2. 実行できない場合、C:\\ffmpeg\\bin\\ffmpeg.exeが存在するかを確認
        3. ファイルがあれば環境変数PATHを設定
        4. 再度ffmpegコマンドが実行可能かを確認

        Returns:
            セットアップ結果
        """
        self._logger.info("Setting up FFMPEG")

        # 想定されるパス
        ffmpeg_dir = Path("C:/ffmpeg/bin")
        ffmpeg_exe = ffmpeg_dir / "ffmpeg.exe"

        # 1. まずffmpegコマンドが実行可能かを確認
        try:
            result = self._command_port.execute_command(
                ["ffmpeg", "-version"],
                timeout=5.0,
            )

            if result.success:
                self._logger.info("FFMPEG is already available via command")
                return SoftwareCheckResult(
                    is_installed=True,
                    version="Installed",
                    installation_path=None  # コマンドで実行可能なのでパスは不明
                )
        except Exception as e:
            self._logger.info("FFMPEG command not available, checking file existence", error=str(e))

        # 2. C:\ffmpeg\bin\ffmpeg.exeが存在するかを確認
        if not ffmpeg_exe.exists():
            self._logger.warning("FFMPEG executable not found", path=str(ffmpeg_exe))
            return SoftwareCheckResult(
                is_installed=False,
                error_message=f"FFMPEGの実行ファイルが見つかりません。\n{ffmpeg_exe} に配置されているか確認してください。",
            )

        # 3. ファイルがあれば環境変数PATHを設定
        try:
            # 現在のPATHを確認
            current_path = os.environ.get("PATH", "")
            target_path_str = str(ffmpeg_dir).replace("/", "\\")
            
            if target_path_str.lower() not in current_path.lower():
                self._logger.info("Adding FFMPEG to PATH", path=target_path_str)
                
                # PowerShellを使用してPATHを追加（Userスコープ）
                ps_command = [
                    "powershell",
                    "-Command",
                    f"[Environment]::SetEnvironmentVariable('Path', [Environment]::GetEnvironmentVariable('Path', 'User') + ';{target_path_str}', 'User')"
                ]
                
                self._command_port.execute_command(ps_command)
                
                # 現在のプロセスの環境変数も更新（以降のチェックのため）
                os.environ["PATH"] = f"{current_path};{target_path_str}"
            else:
                self._logger.info("FFMPEG already in PATH")

        except Exception as e:
            self._logger.error("Failed to update PATH", error=str(e))
            return SoftwareCheckResult(
                is_installed=False,
                error_message=f"環境変数PATHの更新に失敗しました: {e}",
            )

        # 4. 再度ffmpegコマンドが実行可能かを確認
        try:
            # コマンドプロンプト経由で実行してPATHが反映されているか確認
            result = self._command_port.execute_command(
                ["ffmpeg", "-version"],
                timeout=5.0,
            )

            if result.success:
                self._logger.info("FFMPEG setup verification successful")
                return SoftwareCheckResult(
                    is_installed=True,
                    version="Installed",
                    installation_path=ffmpeg_exe
                )
            else:
                # PATHに追加した直後は反映されないことがあるため、フルパスで確認
                result_full = self._command_port.execute_command(
                    [str(ffmpeg_exe), "-version"],
                    timeout=5.0,
                )
                if result_full.success:
                     return SoftwareCheckResult(
                        is_installed=True,
                        version="Installed (Path update pending)",
                        installation_path=ffmpeg_exe
                    )
                
                return SoftwareCheckResult(
                    is_installed=False,
                    error_message="FFMPEGの実行確認に失敗しました",
                )

        except Exception as e:
            self._logger.error("FFMPEG verification failed", error=str(e))
            return SoftwareCheckResult(
                is_installed=False,
                error_message=f"確認中にエラーが発生しました: {e}",
            )

    def setup_tesseract(self) -> SoftwareCheckResult:
        """Tesseractのセットアップを行う。
        
        インストール先（C:\\Program Files\\Tesseract-OCR\\tesseract.exe）を確認し、
        存在する場合はPATHに追加して確認を行う。

        Returns:
            セットアップ結果
        """
        self._logger.info("Setting up Tesseract")

        # 想定されるパス
        tesseract_dir = Path("C:/Program Files/Tesseract-OCR")
        tesseract_exe = tesseract_dir / "tesseract.exe"

        # 1. 実行ファイルの存在確認
        if not tesseract_exe.exists():
            self._logger.warning("Tesseract executable not found", path=str(tesseract_exe))
            return SoftwareCheckResult(
                is_installed=False,
                error_message=f"Tesseractの実行ファイルが見つかりません。\n{tesseract_exe} にインストールされているか確認してください。",
            )

        # 2. PATHへの追加
        try:
            # 現在のPATHを確認
            current_path = os.environ.get("PATH", "")
            target_path_str = str(tesseract_dir).replace("/", "\\")
            
            if target_path_str.lower() not in current_path.lower():
                self._logger.info("Adding Tesseract to PATH", path=target_path_str)
                
                # PowerShellを使用してPATHを追加（Userスコープ）
                ps_command = [
                    "powershell",
                    "-Command",
                    f"[Environment]::SetEnvironmentVariable('Path', [Environment]::GetEnvironmentVariable('Path', 'User') + ';{target_path_str}', 'User')"
                ]
                
                self._command_port.execute_command(ps_command)
                
                # 現在のプロセスの環境変数も更新（以降のチェックのため）
                os.environ["PATH"] = f"{current_path};{target_path_str}"
            else:
                self._logger.info("Tesseract already in PATH")

        except Exception as e:
            self._logger.error("Failed to update PATH", error=str(e))
            return SoftwareCheckResult(
                is_installed=False,
                error_message=f"環境変数PATHの更新に失敗しました: {e}",
            )

        # 3. インストール確認
        try:
            # コマンドプロンプト経由で実行してPATHが反映されているか確認
            result = self._command_port.execute_command(
                ["tesseract", "--version"],
                timeout=5.0,
            )

            if result.success:
                self._logger.info("Tesseract setup verification successful")
                return SoftwareCheckResult(
                    is_installed=True,
                    version="Installed",
                    installation_path=tesseract_exe
                )
            else:
                # PATHに追加した直後は反映されないことがあるため、フルパスで確認
                result_full = self._command_port.execute_command(
                    [str(tesseract_exe), "--version"],
                    timeout=5.0,
                )
                if result_full.success:
                     return SoftwareCheckResult(
                        is_installed=True,
                        version="Installed (Path update pending)",
                        installation_path=tesseract_exe
                    )
                
                return SoftwareCheckResult(
                    is_installed=False,
                    error_message="Tesseractの実行確認に失敗しました",
                )

        except Exception as e:
            self._logger.error("Tesseract verification failed", error=str(e))
            return SoftwareCheckResult(
                is_installed=False,
                error_message=f"確認中にエラーが発生しました: {e}",
            )
