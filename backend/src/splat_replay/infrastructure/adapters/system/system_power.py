"""電源制御アダプタ。"""

from __future__ import annotations

import asyncio
import subprocess
import sys

from structlog.stdlib import BoundLogger

from splat_replay.application.interfaces import PowerPort

_SLEEP_COMMANDS: dict[str, tuple[str, ...]] = {
    "darwin": ("pmset", "sleepnow"),
    "win32": (
        "rundll32.exe",
        "powrprof.dll,SetSuspendState",
        "0,1,0",
    ),
}


class SystemPower(PowerPort):
    """OS の電源制御を提供する。"""

    def __init__(self, logger: BoundLogger) -> None:
        self.logger = logger

    async def sleep(self) -> None:
        """PC をスリープさせる。"""
        try:
            command = _SLEEP_COMMANDS[sys.platform]
        except KeyError as error:
            raise RuntimeError(
                f"この OS では PC スリープをサポートしていません: {sys.platform}"
            ) from error

        self.logger.info("PC スリープ指示")
        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except NotImplementedError:
            await asyncio.to_thread(self._sleep_via_subprocess, command)
            return

        returncode = await process.wait()
        if returncode != 0:
            raise subprocess.CalledProcessError(returncode, command)

    @staticmethod
    def _sleep_via_subprocess(command: tuple[str, ...]) -> None:
        subprocess.run(
            list(command),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
