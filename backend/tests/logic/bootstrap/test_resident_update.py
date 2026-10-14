"""隔離配置先で更新と失敗時復元を実行し、動画・設定を保持する。"""

import base64
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest


def _create_update_roots(tmp_path: Path) -> tuple[Path, Path]:
    source, target = tmp_path / "source", tmp_path / "target"
    for directory, value in ((source, "new"), (target, "old")):
        for name in ("_internal/runtime", "assets/icon", "SplatReplay.exe"):
            file = directory / name
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text(value, encoding="utf-8")
        (directory / "assets/desktop-control.json").write_text(
            '{"version":1}', encoding="utf-8"
        )
    return source, target


def _run_powershell(script: str) -> subprocess.CompletedProcess[str]:
    encoded = base64.b64encode(script.encode("utf-16-le")).decode()
    return subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-EncodedCommand",
            encoded,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
        check=True,
    )


@pytest.mark.parametrize("fail_startup", [False, True])
def test_update_preserves_data_and_rolls_back(
    tmp_path: Path, fail_startup: bool
) -> None:
    if os.name != "nt":
        pytest.skip(
            "update-resident-desktop.ps1 は Windows PowerShell で検証します"
        )
    if shutil.which("powershell") is None:
        pytest.skip(
            "update-resident-desktop.ps1 の検証にはPowerShellが必要です"
        )

    source, target = _create_update_roots(tmp_path)
    for name in (
        "config/settings.toml",
        "videos/recorded/a.mp4",
        "outputs/file",
        "logs/file",
        "assets/thumbnail/ikamodoki1.ttf",
    ):
        file = target / name
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text("keep", encoding="utf-8")
    script_path = (
        Path(__file__).resolve().parents[4]
        / "scripts/update-resident-desktop.ps1"
    )

    def quote(path: Path) -> str:
        return "'" + str(path).replace("'", "''") + "'"

    script = f"""
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
. {quote(script_path)}
function Get-TargetProcesses {{ return @() }}
function Start-Process {{ return $null }}
function Invoke-DesktopCommand {{ return 0 }}
$script:waitCount = 0
function Wait-DesktopState {{ $script:waitCount++; {"if ($script:waitCount -eq 1) { throw 'simulated startup failure' }" if fail_startup else "return"} }}
$failed = $false
try {{ Invoke-ResidentUpdate {quote(source)} {quote(target)} 1 1 }} catch {{ $failed = $true }}
Write-Output ('RESULT:' + (@{{ failed = $failed }} | ConvertTo-Json -Compress))
"""
    result = _run_powershell(script)
    payload = next(
        line[7:]
        for line in result.stdout.splitlines()
        if line.startswith("RESULT:")
    )
    assert json.loads(payload)["failed"] is fail_startup, result.stderr
    assert (target / "SplatReplay.exe").read_text() == (
        "old" if fail_startup else "new"
    )
    for name in (
        "config/settings.toml",
        "videos/recorded/a.mp4",
        "outputs/file",
        "logs/file",
        "assets/thumbnail/ikamodoki1.ttf",
    ):
        assert (target / name).read_text() == "keep"


# integration: Windowsの実プロセス終了コードとOSハンドルの境界を検証する。
@pytest.mark.parametrize(
    ("child_exit_code", "expected_failed", "expected_target"),
    [(0, False, "new"), (17, True, "old")],
)
def test_update_reads_real_process_exit_code(
    tmp_path: Path,
    child_exit_code: int,
    expected_failed: bool,
    expected_target: str,
) -> None:
    if os.name != "nt":
        pytest.skip("実プロセス終了コードの検証にはWindowsが必要です")
    powershell = shutil.which("powershell")
    if powershell is None:
        pytest.skip(
            "実プロセス終了コードの検証にはWindows PowerShellが必要です"
        )
    assert powershell is not None

    source, target = _create_update_roots(tmp_path)
    script_path = (
        Path(__file__).resolve().parents[4]
        / "scripts/update-resident-desktop.ps1"
    )
    child_script = tmp_path / "wait-for-update.ps1"
    child_script.write_text(
        """param([string]$GatePath, [int]$ExitCode)
$deadline = (Get-Date).AddSeconds(60)
while (-not (Test-Path -LiteralPath $GatePath)) {
    if ((Get-Date) -ge $deadline) { exit 91 }
    Start-Sleep -Milliseconds 20
}
exit $ExitCode
""",
        encoding="utf-8",
    )
    gate_path = tmp_path / "update-requested"
    child = subprocess.Popen(
        [
            powershell,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(child_script),
            str(gate_path),
            str(child_exit_code),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=int(getattr(subprocess, "CREATE_NO_WINDOW", 0)),
    )

    def quote(path: Path) -> str:
        return "'" + str(path).replace("'", "''") + "'"

    try:
        script = f"""
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
. {quote(script_path)}
$script:childId = {child.pid}
$script:childPath = (Get-Process -Id $script:childId -ErrorAction Stop).Path
if ([string]::IsNullOrWhiteSpace($script:childPath)) {{ throw 'Child process path was unavailable.' }}
$script:updateRequestCount = 0
function Get-TargetProcesses {{
    $process = Get-Process -Id $script:childId -ErrorAction SilentlyContinue
    if ($null -ne $process -and $process.Path -eq $script:childPath) {{ return @($process) }}
    return @()
}}
function Invoke-DesktopCommand {{
    [CmdletBinding()]param([string]$Executable, [string]$Command)
    if ($Command -eq 'update') {{
        $script:updateRequestCount++
        Set-Content -LiteralPath {quote(gate_path)} -Value 'release'
    }}
    return 0
}}
function Start-Process {{ return $null }}
function Wait-DesktopState {{ return }}
$failed = $false
try {{ Invoke-ResidentUpdate {quote(source)} {quote(target)} 10 10 }} catch {{ $failed = $true }}
Write-Output ('RESULT:' + (@{{ failed = $failed; updateRequestCount = $script:updateRequestCount }} | ConvertTo-Json -Compress))
"""
        result = _run_powershell(script)
        payload = next(
            line[7:]
            for line in result.stdout.splitlines()
            if line.startswith("RESULT:")
        )
        assert json.loads(payload) == {
            "failed": expected_failed,
            "updateRequestCount": 1,
        }, result.stderr
        assert (target / "SplatReplay.exe").read_text() == expected_target
    finally:
        if child.poll() is None:
            child.terminate()
        try:
            child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait(timeout=5)


def test_update_aborts_before_request_when_process_handle_is_unavailable(
    tmp_path: Path,
) -> None:
    if os.name != "nt":
        pytest.skip("実プロセス終了コードの検証にはWindowsが必要です")
    if shutil.which("powershell") is None:
        pytest.skip(
            "実プロセス終了コードの検証にはWindows PowerShellが必要です"
        )

    source, target = _create_update_roots(tmp_path)
    script_path = (
        Path(__file__).resolve().parents[4]
        / "scripts/update-resident-desktop.ps1"
    )

    def quote(path: Path) -> str:
        return "'" + str(path).replace("'", "''") + "'"

    script = f"""
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
. {quote(script_path)}
$script:updateRequestCount = 0
function Get-TargetProcesses {{ return @(New-Object System.Diagnostics.Process) }}
function Invoke-DesktopCommand {{
    [CmdletBinding()]param([string]$Executable, [string]$Command)
    if ($Command -eq 'update') {{ $script:updateRequestCount++ }}
    return 0
}}
function Start-Process {{ return $null }}
function Wait-DesktopState {{ return }}
$failed = $false
try {{ Invoke-ResidentUpdate {quote(source)} {quote(target)} 10 10 }} catch {{ $failed = $true }}
Write-Output ('RESULT:' + (@{{ failed = $failed; updateRequestCount = $script:updateRequestCount }} | ConvertTo-Json -Compress))
"""
    result = _run_powershell(script)
    payload = next(
        line[7:]
        for line in result.stdout.splitlines()
        if line.startswith("RESULT:")
    )
    assert json.loads(payload) == {"failed": True, "updateRequestCount": 0}, (
        result.stderr
    )
    assert (target / "SplatReplay.exe").read_text() == "old"


def test_legacy_deploy_only_targets_its_executable() -> None:
    if os.name != "nt":
        pytest.skip("deploy-desktop.ps1 は Windows PowerShell で検証します")
    if shutil.which("powershell") is None:
        pytest.skip("deploy-desktop.ps1 の検証にはPowerShellが必要です")

    path = Path(__file__).resolve().parents[4] / "scripts/deploy-desktop.ps1"
    quoted = "'" + str(path).replace("'", "''") + "'"
    script = f"""
$ErrorActionPreference = 'Stop'
$ast = [Management.Automation.Language.Parser]::ParseFile({quoted}, [ref]$null, [ref]$null)
$functions = $ast.FindAll({{ param($node) $node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -in @('ConvertTo-Array', 'Get-BlockingProcesses') }}, $true)
foreach ($function in $functions) {{ Invoke-Expression $function.Extent.Text }}
function Get-Process {{
    [CmdletBinding()]param([string]$Name)
    return @(
        [pscustomobject]@{{ ProcessName='SplatReplay'; Id=1; Path='C:\\target\\SplatReplay.exe'; MainWindowHandle=1; MainWindowTitle='target' }},
        [pscustomobject]@{{ ProcessName='SplatReplay'; Id=2; Path='C:\\other\\SplatReplay.exe'; MainWindowHandle=2; MainWindowTitle='other' }},
        [pscustomobject]@{{ ProcessName='obs64'; Id=3; Path='C:\\OBS\\obs64.exe'; MainWindowHandle=3; MainWindowTitle='OBS' }}
    )
}}
$selected = @(Get-BlockingProcesses -Executable 'C:\\target\\SplatReplay.exe')
if ($selected.Count -ne 1 -or $selected[0].id -ne 1) {{ throw 'Unexpected process selected' }}
"""
    encoded = base64.b64encode(script.encode("utf-16-le")).decode()
    subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-EncodedCommand",
            encoded,
        ],
        capture_output=True,
        timeout=30,
        check=True,
    )
