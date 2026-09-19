"""Windows の実子プロセスでコンソール抑止と出力取得を確認する。"""

import sys
from unittest.mock import MagicMock

import pytest

from splat_replay.infrastructure.adapters.system.system_command_adapter import (
    SystemCommandAdapter,
)
from splat_replay.infrastructure.adapters.video.ffmpeg_processor import (
    FFmpegProcessor,
)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows のコンソール契約")
@pytest.mark.parametrize(
    "route", ["text", "progress", "binary", "fallback", "system"]
)
@pytest.mark.asyncio
async def test_child_has_no_console_and_preserves_output(route: str) -> None:
    command = [
        sys.executable,
        "-c",
        "import ctypes, sys; "
        "assert ctypes.windll.kernel32.GetConsoleWindow() == 0; "
        "print('output'); print('error', file=sys.stderr)",
    ]
    processor = FFmpegProcessor(MagicMock())
    if route == "system":
        result = SystemCommandAdapter(MagicMock()).execute_command(command, 10)
        assert result.return_code == 0
        assert result.stdout.strip() == "output"
        assert result.stderr.strip() == "error"
        return
    if route == "text":
        completed = await processor._run_text(command, timeout=10)
    elif route == "progress":
        completed = await processor._run_with_progress(
            command, 1, lambda _percent, _message: None
        )
    elif route == "binary":
        completed = await processor._run_binary(command, timeout=10)
    else:
        completed = await processor._run_binary_fallback(command, timeout=10)
    assert completed.returncode == 0
    assert completed.stdout.strip() in ("output", b"output")
    assert completed.stderr.strip() in ("error", b"error")
