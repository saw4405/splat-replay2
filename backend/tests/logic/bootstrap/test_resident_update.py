"""隔離配置先で更新と失敗時復元を実行し、動画・設定を保持する。"""

import base64
import json
import subprocess
from pathlib import Path

import pytest


@pytest.mark.parametrize("fail_startup", [False, True])
def test_update_preserves_data_and_rolls_back(
    tmp_path: Path, fail_startup: bool
) -> None:
    source, target = tmp_path / "source", tmp_path / "target"
    for directory, value in ((source, "new"), (target, "old")):
        for name in ("_internal/runtime", "assets/icon", "SplatReplay.exe"):
            file = directory / name
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text(value, encoding="utf-8")
        (directory / "assets/desktop-control.json").write_text(
            '{"version":1}', encoding="utf-8"
        )
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
    encoded = base64.b64encode(script.encode("utf-16-le")).decode()
    result = subprocess.run(
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


def test_legacy_deploy_only_targets_its_executable() -> None:
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
