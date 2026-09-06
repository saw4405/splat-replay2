from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Callable, cast

import pytest
from pydantic import SecretStr

from splat_replay.domain.exceptions import DeviceError
from splat_replay.domain.config import OBSSettings
from splat_replay.infrastructure.adapters.obs import (
    process_manager as process_module,
)
from splat_replay.infrastructure.adapters.obs.process_manager import (
    OBSProcessManager,
)
from splat_replay.infrastructure.adapters.obs.recorder_controller import (
    OBSRecorderController,
)


class _LoggerStub:
    def debug(self, event: str, **kw: object) -> None:
        return None

    def info(self, event: str, **kw: object) -> None:
        return None

    def warning(self, event: str, **kw: object) -> None:
        return None

    def error(self, event: str, **kw: object) -> None:
        return None


class _PopenStub:
    def __init__(self, pid: int) -> None:
        self.pid = pid
        self.returncode: int | None = None

    def poll(self) -> int | None:
        return self.returncode

    def wait(self) -> int:
        if self.returncode is None:
            self.returncode = 0
        return self.returncode

    def terminate(self) -> None:
        self.returncode = 1

    def close(self) -> None:
        self.returncode = 0


class _PsutilProcessStub:
    def __init__(self, pid: int) -> None:
        self.pid = pid
        self.alive = True
        self.terminated = False

    def is_running(self) -> bool:
        return self.alive

    def status(self) -> str:
        return "running"

    def wait(self) -> int:
        self.alive = False
        return 0

    def terminate(self) -> None:
        self.terminated = True
        self.alive = False

    def close(self) -> None:
        self.alive = False


class _ProcessInfoStub(_PsutilProcessStub):
    def __init__(self, pid: int, *, name: str, exe: Path | None) -> None:
        super().__init__(pid)
        self.info: dict[str, object] = {
            "name": name,
            "exe": str(exe) if exe is not None else None,
        }


class _Win32ApiStub:
    def __init__(
        self,
        on_close: Callable[[], None] | None = None,
        on_message: Callable[[int, int], None] | None = None,
        on_key: Callable[[int], None] | None = None,
    ) -> None:
        self.closed_windows: list[int] = []
        self.key_events: list[tuple[int, int]] = []
        self._on_close = on_close
        self._on_message = on_message
        self._on_key = on_key

    def PostMessage(
        self, hwnd: int, msg: int, wparam: int, lparam: int
    ) -> None:
        _ = msg, wparam, lparam
        self.closed_windows.append(hwnd)
        if self._on_message is not None:
            self._on_message(hwnd, msg)
        if self._on_close is not None:
            self._on_close()

    def keybd_event(
        self, vk: int, scan: int, flags: int, extra_info: int
    ) -> None:
        _ = scan, extra_info
        self.key_events.append((vk, flags))
        if flags == 0 and self._on_key is not None:
            self._on_key(vk)


class _Win32ConStub:
    WM_CLOSE = 0x0010
    BM_CLICK = 0x00F5
    VK_RETURN = 0x0D
    KEYEVENTF_KEYUP = 0x0002


class _Win32GuiStub:
    def __init__(
        self,
        *,
        titles: dict[int, str],
        classes: dict[int, str],
        children: dict[int, list[int]],
    ) -> None:
        self._titles = titles
        self._classes = classes
        self._children = children
        self.foreground_windows: list[int] = []

    def GetWindowText(self, hwnd: int) -> str:
        return self._titles.get(hwnd, "")

    def GetClassName(self, hwnd: int) -> str:
        return self._classes.get(hwnd, "")

    def SetForegroundWindow(self, hwnd: int) -> None:
        self.foreground_windows.append(hwnd)

    def EnumChildWindows(
        self,
        hwnd: int,
        callback: Callable[[int, object], bool],
        param: object,
    ) -> None:
        for child_hwnd in self._children.get(hwnd, []):
            if not callback(child_hwnd, param):
                break


@pytest.mark.asyncio
async def test_process_lookup_requires_exact_executable_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    configured_exe = tmp_path / "configured" / "obs64.exe"
    manager = OBSProcessManager(configured_exe, cast(Any, _LoggerStub()))
    other = _ProcessInfoStub(
        100, name="obs64.exe", exe=tmp_path / "other" / "obs64.exe"
    )
    matching = _ProcessInfoStub(200, name="obs64.exe", exe=configured_exe)
    monkeypatch.setattr(
        process_module.psutil,
        "process_iter",
        lambda attrs: [other, matching],
    )

    found = await manager._find_existing_obs_process()

    assert found is matching


@pytest.mark.asyncio
async def test_process_lookup_rejects_multiple_matching_instances(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    configured_exe = tmp_path / "obs64.exe"
    manager = OBSProcessManager(configured_exe, cast(Any, _LoggerStub()))
    monkeypatch.setattr(
        process_module.psutil,
        "process_iter",
        lambda attrs: [
            _ProcessInfoStub(100, name="obs64.exe", exe=configured_exe),
            _ProcessInfoStub(200, name="obs64.exe", exe=configured_exe),
        ],
    )

    found = await manager._find_existing_obs_process()

    assert found is None


@pytest.mark.asyncio
async def test_process_manager_recovery_preserves_nonmatching_process(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    manager = OBSProcessManager(
        tmp_path / "obs64.exe", cast(Any, _LoggerStub())
    )

    async def no_matching_process() -> None:
        return None

    monkeypatch.setattr(
        manager, "_find_existing_obs_process", no_matching_process
    )

    restarted = await manager.restart_for_recovery()

    assert restarted is False


@pytest.mark.asyncio
async def test_process_manager_recovery_replaces_managed_process(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    manager = OBSProcessManager(
        tmp_path / "obs64.exe", cast(Any, _LoggerStub())
    )
    process = _PopenStub(pid=1234)
    manager._process = cast(Any, process)
    calls: list[str] = []

    async def _teardown_locked() -> None:
        calls.append("teardown")
        process.close()
        manager._process = None

    async def _launch_locked() -> None:
        calls.append("launch")
        manager._process = cast(Any, _PopenStub(pid=5678))

    monkeypatch.setattr(manager, "_teardown_locked", _teardown_locked)
    monkeypatch.setattr(manager, "_launch_locked", _launch_locked)

    restarted = await manager.restart_for_recovery()

    assert restarted is True
    assert calls == ["teardown", "launch"]


@pytest.mark.asyncio
async def test_recovery_of_preexisting_obs_preserves_replacement_on_teardown(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    manager = OBSProcessManager(
        tmp_path / "obs64.exe", cast(Any, _LoggerStub())
    )
    existing_process = _PsutilProcessStub(pid=1234)
    replacement = _PopenStub(pid=5678)
    teardown_calls = 0

    async def find_existing() -> _PsutilProcessStub:
        return existing_process

    async def teardown_locked() -> None:
        nonlocal teardown_calls
        teardown_calls += 1
        assert manager._process is existing_process
        existing_process.close()
        manager._process = None

    async def launch_locked() -> None:
        manager._process = cast(Any, replacement)

    monkeypatch.setattr(manager, "_find_existing_obs_process", find_existing)
    monkeypatch.setattr(manager, "_teardown_locked", teardown_locked)
    monkeypatch.setattr(manager, "_launch_locked", launch_locked)

    restarted = await manager.restart_for_recovery()
    await manager.teardown()

    assert restarted is True
    assert teardown_calls == 1
    assert replacement.poll() is None


@pytest.mark.asyncio
async def test_process_manager_does_not_launch_again_for_owned_live_process(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    obs_exe = tmp_path / "obs64.exe"
    obs_exe.write_bytes(b"")
    manager = OBSProcessManager(obs_exe, cast(Any, _LoggerStub()))
    running_checks = iter([False, True, False, True])
    popen_calls: list[list[str]] = []

    async def fake_is_running() -> bool:
        return next(running_checks)

    async def run_inline(
        func: object, *args: object, **kwargs: object
    ) -> object:
        return cast(Any, func)(*args, **kwargs)

    async def no_sleep(_: float) -> None:
        return None

    def fake_popen(
        args: list[str],
        *,
        cwd: str,
        creationflags: int,
    ) -> _PopenStub:
        _ = cwd, creationflags
        popen_calls.append(args)
        return _PopenStub(pid=1000 + len(popen_calls))

    monkeypatch.setattr(manager, "is_running", fake_is_running)
    monkeypatch.setattr(process_module.asyncio, "to_thread", run_inline)
    monkeypatch.setattr(process_module.asyncio, "sleep", no_sleep)
    monkeypatch.setattr(process_module.subprocess, "Popen", fake_popen)

    await manager.launch()
    await manager.launch()

    assert len(popen_calls) == 1
    assert popen_calls[0] == [str(obs_exe)]


@pytest.mark.asyncio
async def test_process_manager_launch_timeout_cleans_started_process(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    obs_exe = tmp_path / "obs64.exe"
    obs_exe.write_bytes(b"")
    manager = OBSProcessManager(obs_exe, cast(Any, _LoggerStub()))
    process = _PopenStub(pid=1234)

    async def fake_is_running() -> bool:
        return False

    async def run_inline(
        func: object, *args: object, **kwargs: object
    ) -> object:
        return cast(Any, func)(*args, **kwargs)

    async def no_sleep(_: float) -> None:
        return None

    def fake_popen(
        args: list[str],
        *,
        cwd: str,
        creationflags: int,
    ) -> _PopenStub:
        _ = args, cwd, creationflags
        return process

    monkeypatch.setattr(manager, "is_running", fake_is_running)
    monkeypatch.setattr(manager, "find_window_by_pid", lambda pid: [])
    monkeypatch.setattr(process_module.asyncio, "to_thread", run_inline)
    monkeypatch.setattr(process_module.asyncio, "sleep", no_sleep)
    monkeypatch.setattr(process_module.subprocess, "Popen", fake_popen)

    with pytest.raises(DeviceError):
        await manager.launch()

    assert process.returncode == 1
    assert manager._process is None


@pytest.mark.asyncio
async def test_process_manager_launch_continues_from_obs_crash_dialog(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    obs_exe = tmp_path / "obs64.exe"
    obs_exe.write_bytes(b"")
    manager = OBSProcessManager(obs_exe, cast(Any, _LoggerStub()))
    running_checks = iter([False, False, True])
    clicked_buttons: list[int] = []

    async def fake_is_running() -> bool:
        return next(running_checks)

    async def run_inline(
        func: object, *args: object, **kwargs: object
    ) -> object:
        return cast(Any, func)(*args, **kwargs)

    async def no_sleep(_: float) -> None:
        return None

    def fake_popen(
        args: list[str],
        *,
        cwd: str,
        creationflags: int,
    ) -> _PopenStub:
        _ = args, cwd, creationflags
        return _PopenStub(pid=1234)

    def on_message(hwnd: int, msg: int) -> None:
        if hwnd == 402 and msg == _Win32ConStub.BM_CLICK:
            clicked_buttons.append(hwnd)

    win32api = _Win32ApiStub(on_message=on_message)
    win32gui = _Win32GuiStub(
        titles={
            401: "OBS Studioのクラッシュが検出されました",
            402: "通常モードで実行",
        },
        classes={401: "#32770", 402: "Button"},
        children={401: [402]},
    )

    monkeypatch.setattr(manager, "is_running", fake_is_running)
    monkeypatch.setattr(manager, "find_window_by_pid", lambda pid: [401])
    monkeypatch.setattr(process_module, "win32com_client", None)
    monkeypatch.setattr(process_module, "win32api", win32api)
    monkeypatch.setattr(process_module, "win32con", _Win32ConStub())
    monkeypatch.setattr(process_module, "win32gui", win32gui)
    monkeypatch.setattr(process_module.asyncio, "to_thread", run_inline)
    monkeypatch.setattr(process_module.asyncio, "sleep", no_sleep)
    monkeypatch.setattr(process_module.subprocess, "Popen", fake_popen)

    await manager.launch()

    assert clicked_buttons == [402]


@pytest.mark.asyncio
async def test_process_manager_launch_presses_enter_on_qt_crash_dialog(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    obs_exe = tmp_path / "obs64.exe"
    obs_exe.write_bytes(b"")
    manager = OBSProcessManager(obs_exe, cast(Any, _LoggerStub()))
    running_checks = iter([False, False, True])

    async def fake_is_running() -> bool:
        return next(running_checks)

    async def run_inline(
        func: object, *args: object, **kwargs: object
    ) -> object:
        return cast(Any, func)(*args, **kwargs)

    async def no_sleep(_: float) -> None:
        return None

    def fake_popen(
        args: list[str],
        *,
        cwd: str,
        creationflags: int,
    ) -> _PopenStub:
        _ = args, cwd, creationflags
        return _PopenStub(pid=1234)

    win32api = _Win32ApiStub()
    win32gui = _Win32GuiStub(
        titles={401: "OBS Studioのクラッシュが検出されました"},
        classes={401: "QMessageBox"},
        children={401: []},
    )

    monkeypatch.setattr(manager, "is_running", fake_is_running)
    monkeypatch.setattr(manager, "find_window_by_pid", lambda pid: [401])
    monkeypatch.setattr(process_module, "win32com_client", None)
    monkeypatch.setattr(process_module, "win32api", win32api)
    monkeypatch.setattr(process_module, "win32con", _Win32ConStub())
    monkeypatch.setattr(process_module, "win32gui", win32gui)
    monkeypatch.setattr(process_module.asyncio, "to_thread", run_inline)
    monkeypatch.setattr(process_module.asyncio, "sleep", no_sleep)
    monkeypatch.setattr(process_module.subprocess, "Popen", fake_popen)

    await manager.launch()

    assert win32gui.foreground_windows == [401]
    assert win32api.key_events == [
        (_Win32ConStub.VK_RETURN, 0),
        (_Win32ConStub.VK_RETURN, _Win32ConStub.KEYEVENTF_KEYUP),
    ]


@pytest.mark.asyncio
async def test_process_manager_teardown_closes_owned_process_even_if_running_check_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    obs_exe = tmp_path / "obs64.exe"
    obs_exe.write_bytes(b"")
    manager = OBSProcessManager(obs_exe, cast(Any, _LoggerStub()))
    process = _PopenStub(pid=1234)
    manager._process = cast(Any, process)
    win32api = _Win32ApiStub(on_close=process.close)
    win32gui = _Win32GuiStub(
        titles={101: "OBS 32.1.1 - プロファイル: 無題 - シーン: 無題"},
        classes={101: "Qt5152QWindowIcon"},
        children={},
    )

    async def fake_is_running() -> bool:
        return False

    async def run_inline(
        func: object, *args: object, **kwargs: object
    ) -> object:
        return cast(Any, func)(*args, **kwargs)

    monkeypatch.setattr(manager, "is_running", fake_is_running)
    monkeypatch.setattr(manager, "find_window_by_pid", lambda pid: [101])
    monkeypatch.setattr(process_module, "win32com_client", None)
    monkeypatch.setattr(process_module, "win32api", win32api)
    monkeypatch.setattr(process_module, "win32con", _Win32ConStub())
    monkeypatch.setattr(process_module, "win32gui", win32gui)
    monkeypatch.setattr(process_module.asyncio, "to_thread", run_inline)

    await manager.teardown()

    assert win32api.closed_windows == [101]
    assert manager._process is None


@pytest.mark.asyncio
async def test_process_manager_teardown_retries_close_while_process_is_alive(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    obs_exe = tmp_path / "obs64.exe"
    obs_exe.write_bytes(b"")
    manager = OBSProcessManager(obs_exe, cast(Any, _LoggerStub()))
    process = _PopenStub(pid=1234)
    manager._process = cast(Any, process)
    close_count = 0

    def on_message(hwnd: int, msg: int) -> None:
        nonlocal close_count
        if hwnd == 101 and msg == _Win32ConStub.WM_CLOSE:
            close_count += 1
            if close_count >= 2:
                process.close()

    win32api = _Win32ApiStub(on_message=on_message)
    win32gui = _Win32GuiStub(
        titles={
            101: "OBS 32.1.1 - プロファイル: 無題 - シーン: 無題",
        },
        classes={101: "Qt5152QWindowIcon"},
        children={},
    )

    async def fake_is_running() -> bool:
        return True

    async def run_inline(
        func: object, *args: object, **kwargs: object
    ) -> object:
        return cast(Any, func)(*args, **kwargs)

    async def no_sleep(_: float) -> None:
        return None

    monkeypatch.setattr(manager, "is_running", fake_is_running)
    monkeypatch.setattr(manager, "find_window_by_pid", lambda pid: [101])
    monkeypatch.setattr(process_module, "win32com_client", None)
    monkeypatch.setattr(process_module, "win32api", win32api)
    monkeypatch.setattr(process_module, "win32con", _Win32ConStub())
    monkeypatch.setattr(process_module, "win32gui", win32gui)
    monkeypatch.setattr(process_module.asyncio, "to_thread", run_inline)
    monkeypatch.setattr(process_module.asyncio, "sleep", no_sleep)

    await manager.teardown()

    assert win32api.closed_windows == [101, 101]
    assert process.returncode == 0
    assert manager._process is None


@pytest.mark.asyncio
async def test_process_manager_teardown_does_not_close_external_process(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    obs_exe = tmp_path / "obs64.exe"
    obs_exe.write_bytes(b"")
    manager = OBSProcessManager(obs_exe, cast(Any, _LoggerStub()))
    existing_process = _PsutilProcessStub(pid=4321)
    win32api = _Win32ApiStub(on_close=existing_process.close)
    win32gui = _Win32GuiStub(
        titles={101: "OBS 32.1.1 - プロファイル: 無題 - シーン: 無題"},
        classes={101: "Qt5152QWindowIcon"},
        children={},
    )

    async def fake_is_running() -> bool:
        return True

    async def fake_find_existing_obs_process() -> _PsutilProcessStub:
        return existing_process

    async def run_inline(
        func: object, *args: object, **kwargs: object
    ) -> object:
        return cast(Any, func)(*args, **kwargs)

    monkeypatch.setattr(manager, "is_running", fake_is_running)
    monkeypatch.setattr(
        manager, "_find_existing_obs_process", fake_find_existing_obs_process
    )
    monkeypatch.setattr(manager, "find_window_by_pid", lambda pid: [101])
    monkeypatch.setattr(process_module, "win32com_client", None)
    monkeypatch.setattr(process_module, "win32api", win32api)
    monkeypatch.setattr(process_module, "win32con", _Win32ConStub())
    monkeypatch.setattr(process_module, "win32gui", win32gui)
    monkeypatch.setattr(process_module.asyncio, "to_thread", run_inline)

    await manager.teardown()

    assert win32api.closed_windows == []
    assert existing_process.alive is True
    assert manager._process is None


@pytest.mark.asyncio
async def test_process_manager_teardown_confirms_obs_exit_dialog(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    obs_exe = tmp_path / "obs64.exe"
    obs_exe.write_bytes(b"")
    manager = OBSProcessManager(obs_exe, cast(Any, _LoggerStub()))
    process = _PopenStub(pid=1234)
    manager._process = cast(Any, process)
    window_sequences = iter([[201], [202]])

    async def fake_is_running() -> bool:
        return True

    async def run_inline(
        func: object, *args: object, **kwargs: object
    ) -> object:
        return cast(Any, func)(*args, **kwargs)

    async def no_sleep(_: float) -> None:
        return None

    def fake_find_window_by_pid(pid: int) -> list[int]:
        _ = pid
        return next(window_sequences, [202])

    def on_message(hwnd: int, msg: int) -> None:
        if hwnd == 303 and msg == _Win32ConStub.BM_CLICK:
            process.close()

    win32api = _Win32ApiStub(on_message=on_message)
    win32gui = _Win32GuiStub(
        titles={
            201: "OBS 32.1.1 - プロファイル: 無題 - シーン: 無題",
            202: "OBS",
            303: "はい(&Y)",
        },
        classes={201: "Qt5152QWindowIcon", 202: "#32770", 303: "Button"},
        children={202: [303]},
    )

    monkeypatch.setattr(manager, "is_running", fake_is_running)
    monkeypatch.setattr(manager, "find_window_by_pid", fake_find_window_by_pid)
    monkeypatch.setattr(process_module, "win32com_client", None)
    monkeypatch.setattr(process_module, "win32api", win32api)
    monkeypatch.setattr(process_module, "win32con", _Win32ConStub())
    monkeypatch.setattr(process_module, "win32gui", win32gui)
    monkeypatch.setattr(process_module.asyncio, "to_thread", run_inline)
    monkeypatch.setattr(process_module.asyncio, "sleep", no_sleep)

    await manager.teardown()

    assert win32api.closed_windows == [201, 303]
    assert process.returncode == 0
    assert manager._process is None


@pytest.mark.asyncio
async def test_process_manager_teardown_presses_enter_on_qt_exit_dialog(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    obs_exe = tmp_path / "obs64.exe"
    obs_exe.write_bytes(b"")
    manager = OBSProcessManager(obs_exe, cast(Any, _LoggerStub()))
    process = _PopenStub(pid=1234)
    manager._process = cast(Any, process)
    window_sequences = iter([[201], [202]])

    async def fake_is_running() -> bool:
        return True

    async def run_inline(
        func: object, *args: object, **kwargs: object
    ) -> object:
        return cast(Any, func)(*args, **kwargs)

    async def no_sleep(_: float) -> None:
        return None

    def fake_find_window_by_pid(pid: int) -> list[int]:
        _ = pid
        return next(window_sequences, [202])

    def on_key(vk: int) -> None:
        if vk == _Win32ConStub.VK_RETURN:
            process.close()

    win32api = _Win32ApiStub(on_key=on_key)
    win32gui = _Win32GuiStub(
        titles={
            201: "OBS 32.1.1 - プロファイル: 無題 - シーン: 無題",
            202: "OBS",
        },
        classes={201: "Qt5152QWindowIcon", 202: "QMessageBox"},
        children={},
    )

    monkeypatch.setattr(manager, "is_running", fake_is_running)
    monkeypatch.setattr(manager, "find_window_by_pid", fake_find_window_by_pid)
    monkeypatch.setattr(process_module, "win32com_client", None)
    monkeypatch.setattr(process_module, "win32api", win32api)
    monkeypatch.setattr(process_module, "win32con", _Win32ConStub())
    monkeypatch.setattr(process_module, "win32gui", win32gui)
    monkeypatch.setattr(process_module.asyncio, "to_thread", run_inline)
    monkeypatch.setattr(process_module.asyncio, "sleep", no_sleep)

    await manager.teardown()

    assert win32api.closed_windows == [201]
    assert win32gui.foreground_windows == [202]
    assert win32api.key_events == [
        (_Win32ConStub.VK_RETURN, 0),
        (_Win32ConStub.VK_RETURN, _Win32ConStub.KEYEVENTF_KEYUP),
    ]
    assert process.returncode == 0
    assert manager._process is None


@pytest.mark.asyncio
async def test_process_manager_teardown_uses_uia_for_qt_exit_dialog(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    obs_exe = tmp_path / "obs64.exe"
    obs_exe.write_bytes(b"")
    manager = OBSProcessManager(obs_exe, cast(Any, _LoggerStub()))
    process = _PopenStub(pid=1234)
    manager._process = cast(Any, process)
    window_sequences = iter([[201], [202]])
    uia_calls: list[tuple[int, tuple[str, ...]]] = []

    async def fake_is_running() -> bool:
        return True

    async def run_inline(
        func: object, *args: object, **kwargs: object
    ) -> object:
        return cast(Any, func)(*args, **kwargs)

    async def no_sleep(_: float) -> None:
        return None

    def fake_find_window_by_pid(pid: int) -> list[int]:
        _ = pid
        return next(window_sequences, [202])

    def fake_invoke_uia_button_by_labels(
        pid: int,
        labels: tuple[str, ...],
        *,
        window_title_tokens: tuple[str, ...] = (),
        window_class_names: tuple[str, ...] = (),
    ) -> tuple[str, str] | None:
        _ = window_title_tokens, window_class_names
        uia_calls.append((pid, labels))
        if process.returncode is None and len(uia_calls) >= 2:
            process.close()
            return ("OBS", "はい")
        return None

    win32api = _Win32ApiStub()
    win32gui = _Win32GuiStub(
        titles={
            201: "OBS 32.1.1 - プロファイル: 無題 - シーン: 無題",
            202: "OBS",
        },
        classes={201: "Qt5152QWindowIcon", 202: "QMessageBox"},
        children={},
    )

    monkeypatch.setattr(manager, "is_running", fake_is_running)
    monkeypatch.setattr(manager, "find_window_by_pid", fake_find_window_by_pid)
    monkeypatch.setattr(
        manager,
        "_invoke_uia_button_by_labels",
        fake_invoke_uia_button_by_labels,
    )
    monkeypatch.setattr(process_module, "win32api", win32api)
    monkeypatch.setattr(process_module, "win32con", _Win32ConStub())
    monkeypatch.setattr(process_module, "win32gui", win32gui)
    monkeypatch.setattr(process_module.asyncio, "to_thread", run_inline)
    monkeypatch.setattr(process_module.asyncio, "sleep", no_sleep)

    await manager.teardown()

    assert win32api.closed_windows == [201]
    assert uia_calls
    assert process.returncode == 0
    assert manager._process is None


class _ProcessManagerSpy:
    def __init__(self, events: list[str]) -> None:
        self.events = events
        self.running = False
        self.launch_started = asyncio.Event()
        self.release_launch = asyncio.Event()
        self.teardown_started = asyncio.Event()

    async def is_running(self) -> bool:
        return self.running

    async def launch(self) -> None:
        self.events.append("process.launch:start")
        self.launch_started.set()
        await self.release_launch.wait()
        self.running = True
        self.events.append("process.launch:end")

    async def teardown(self) -> None:
        self.events.append("process.teardown")
        self.running = False
        self.teardown_started.set()


class _OBSResponseStub:
    def __init__(self, res_data: dict[str, object] | None) -> None:
        self.res_data = res_data


class _WebSocketSpy:
    def __init__(self, events: list[str]) -> None:
        self.events = events
        self.is_connected = False
        self.virtual_camera_active = False
        self.meter_started = asyncio.Event()
        self.release_meter = asyncio.Event()
        self.disconnect_started = asyncio.Event()

    async def connect(self) -> None:
        self.events.append("ws.connect")
        self.is_connected = True

    async def disconnect(self) -> None:
        self.events.append("ws.disconnect")
        self.is_connected = False
        self.disconnect_started.set()

    async def request(
        self,
        request_type: str,
        idempotent: bool = False,
        request_data: dict[str, object] | None = None,
    ) -> _OBSResponseStub:
        _ = idempotent, request_data
        self.events.append(f"ws.request:{request_type}")
        if request_type == "GetRecordStatus":
            return _OBSResponseStub(
                {"outputActive": False, "outputPaused": False}
            )
        if request_type == "StartVirtualCam":
            self.virtual_camera_active = True
            return _OBSResponseStub({})
        if request_type == "StopVirtualCam":
            self.virtual_camera_active = False
            return _OBSResponseStub({})
        if request_type == "GetInputList":
            return _OBSResponseStub({"inputs": [{"inputName": "MiraBox"}]})
        if request_type == "GetInputMute":
            return _OBSResponseStub({"inputMuted": False})
        if request_type == "GetInputAudioTracks":
            return _OBSResponseStub({"inputAudioTracks": {"1": True}})
        if request_type == "GetSourceActive":
            return _OBSResponseStub({"videoActive": True})
        raise AssertionError(f"Unexpected OBS request: {request_type}")

    async def get_data(self, request_type: str, key: str) -> object | None:
        self.events.append(f"ws.get_data:{request_type}:{key}")
        if request_type == "GetVirtualCamStatus":
            return self.virtual_camera_active
        return None

    async def collect_input_volume_meter_events(
        self, input_name: str, *, sample_duration_seconds: float
    ) -> list[dict[str, object]]:
        _ = input_name, sample_duration_seconds
        self.events.append("ws.meter:start")
        self.meter_started.set()
        await self.release_meter.wait()
        self.events.append("ws.meter:end")
        return [{"inputLevelsMul": [0.5], "inputLevelsDb": [-6.0]}]


def _controller_with_spies(
    process_manager: _ProcessManagerSpy,
    ws_client: _WebSocketSpy,
) -> OBSRecorderController:
    controller = OBSRecorderController(
        OBSSettings(websocket_password=SecretStr("")),
        cast(Any, _LoggerStub()),
    )
    controller._process_manager = cast(Any, process_manager)
    controller._ws_client = cast(Any, ws_client)
    return controller


@pytest.mark.asyncio
async def test_setup_and_teardown_do_not_overlap_lifecycle_operations() -> (
    None
):
    events: list[str] = []
    process_manager = _ProcessManagerSpy(events)
    ws_client = _WebSocketSpy(events)
    controller = _controller_with_spies(process_manager, ws_client)

    setup_task = asyncio.create_task(controller.setup())
    await process_manager.launch_started.wait()
    teardown_task = asyncio.create_task(controller.teardown())
    await asyncio.sleep(0.01)
    process_manager.release_launch.set()
    await process_manager.teardown_started.wait()

    await asyncio.gather(setup_task, teardown_task)

    assert events.index("ws.request:StartVirtualCam") < events.index(
        "process.teardown"
    )


@pytest.mark.asyncio
async def test_audio_health_check_and_teardown_do_not_overlap_obs_operations() -> (
    None
):
    events: list[str] = []
    process_manager = _ProcessManagerSpy(events)
    process_manager.running = True
    ws_client = _WebSocketSpy(events)
    controller = _controller_with_spies(process_manager, ws_client)

    health_task = asyncio.create_task(
        controller.check_audio_input_health(
            "MiraBox", sample_duration_seconds=0.1
        )
    )
    await ws_client.meter_started.wait()
    teardown_task = asyncio.create_task(controller.teardown())
    await asyncio.sleep(0.01)
    ws_client.release_meter.set()
    await ws_client.disconnect_started.wait()

    await asyncio.gather(health_task, teardown_task)

    assert events.index("ws.meter:end") < events.index("process.teardown")
