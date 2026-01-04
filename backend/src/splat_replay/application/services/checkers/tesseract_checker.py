"""Tesseract インストール状態チェッカー。"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from splat_replay.application.interfaces import (
    CommandExecutionError,
    FileSystemPort,
    LoggerPort,
    SystemCommandPort,
)
from splat_replay.application.services.setup.system_check_service import (
    SoftwareCheckResult,
)


class TesseractChecker:
    """Tesseract OCR のインストール状態を確認するチェッカー。"""

    def __init__(
        self,
        command_port: SystemCommandPort,
        logger: LoggerPort,
        file_system: FileSystemPort,
    ) -> None:
        """チェッカーを初期化する。

        Args:
            command_port: システムコマンド実行ポート
            logger: ロガーポート
        """
        self._command_port = command_port
        self._logger = logger
        self._file_system = file_system

    def check(self) -> SoftwareCheckResult:
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

        if self._file_system.is_file(tesseract_exe):
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
