"""Homebrew 経由の FFmpeg / Tesseract / FLAC 導入 adapter。"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from typing import Literal

from structlog.stdlib import BoundLogger

from splat_replay.application.interfaces import (
    CommandExecutionError,
    SoftwareInstallAttempt,
    SoftwareInstallerPort,
    SystemCommandPort,
)

_HOMEBREW_INSTALL_URL = (
    "https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh"
)
_FORMULAE: dict[Literal["ffmpeg", "tesseract", "flac"], tuple[str, ...]] = {
    "ffmpeg": ("ffmpeg",),
    "tesseract": ("tesseract", "tesseract-lang"),
    "flac": ("flac",),
}
_BREW_INSTALL_TIMEOUT_SECONDS = 30 * 60


class HomebrewSoftwareInstaller(SoftwareInstallerPort):
    """macOS software install commands, with interactive first-run setup."""

    def __init__(
        self, command_port: SystemCommandPort, logger: BoundLogger
    ) -> None:
        self._command_port = command_port
        self._logger = logger

    def install(
        self, software: Literal["ffmpeg", "tesseract", "flac"]
    ) -> SoftwareInstallAttempt:
        formulae = _FORMULAE.get(software)
        if formulae is None:
            return SoftwareInstallAttempt(
                completed=False,
                error_message="このソフトウェアの自動導入には対応していません",
            )
        if sys.platform != "darwin":
            return SoftwareInstallAttempt(
                completed=False,
                error_message="Homebrew による導入は macOS でのみ利用できます",
            )

        if self._command_port.check_command_exists("brew"):
            try:
                result = self._command_port.execute_command(
                    ["brew", "install", *formulae],
                    # ponytail: 30分上限。超える formula は background job 化する。
                    timeout=_BREW_INSTALL_TIMEOUT_SECONDS,
                )
            except CommandExecutionError as exc:
                self._logger.warning(
                    "Homebrew installation failed", software=software
                )
                return SoftwareInstallAttempt(
                    completed=False,
                    error_message=f"Homebrew による導入に失敗しました: {exc}",
                )
            if result.success:
                return SoftwareInstallAttempt(completed=True)
            return SoftwareInstallAttempt(
                completed=False,
                error_message=(
                    result.stderr.strip()
                    or "Homebrew による導入に失敗しました"
                ),
            )

        return self._install_from_terminal(formulae)

    def _install_from_terminal(
        self, formulae: tuple[str, ...]
    ) -> SoftwareInstallAttempt:
        script = (
            "#!/bin/bash\n"
            'script_path="$0"\n'
            "trap 'rm -f \"$script_path\"' EXIT\n"
            f'/bin/bash -c "$(/usr/bin/curl -fsSL {_HOMEBREW_INSTALL_URL})" '
            '&& eval "$(/opt/homebrew/bin/brew shellenv)" '
            f"&& /opt/homebrew/bin/brew install {' '.join(formulae)}\n"
            "status=$?\n"
            'if [ "$status" -eq 0 ]; then\n'
            '  echo "導入が完了しました。"\n'
            "else\n"
            '  echo "導入に失敗しました。上のエラーを確認してください。"\n'
            "fi\n"
            'read -r -p "Enter を押すと Terminal を閉じます。"\n'
            'exit "$status"\n'
        )
        script_path: Path | None = None
        terminal_started = False
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                suffix=".command",
                encoding="utf-8",
                delete=False,
            ) as handle:
                handle.write(script)
                script_path = Path(handle.name)
            script_path.chmod(0o700)
            result = self._command_port.execute_command(
                ["/usr/bin/open", "-a", "Terminal", str(script_path)],
                timeout=10.0,
            )
            terminal_started = result.success
        except CommandExecutionError as exc:
            return SoftwareInstallAttempt(
                completed=False,
                error_message=f"Terminal を起動できませんでした: {exc}",
            )
        except OSError as exc:
            return SoftwareInstallAttempt(
                completed=False,
                error_message=f"Terminal 用の導入ファイルを作成できませんでした: {exc}",
            )
        finally:
            if script_path is not None and not terminal_started:
                self._remove_script(script_path)

        if not result.success:
            detail = result.stderr.strip() or "open コマンドに失敗しました"
            return SoftwareInstallAttempt(
                completed=False,
                error_message=f"Terminal を起動できませんでした: {detail}",
            )

        self._logger.info("Homebrew installer opened in Terminal")
        return SoftwareInstallAttempt(
            completed=False,
            error_message=(
                "Terminal で Homebrew の導入を開始しました。表示された確認を行い、"
                "完了後にこの画面でインストール状態を再確認してください。"
            ),
        )

    def _remove_script(self, path: Path) -> None:
        try:
            path.unlink(missing_ok=True)
        except OSError as exc:
            self._logger.warning(
                "Temporary Homebrew install script cleanup failed",
                error=str(exc),
            )
