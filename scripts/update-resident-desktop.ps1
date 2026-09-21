[CmdletBinding()]
param(
    [string]$SourceDir,
    [string]$DestinationDir,
    [int]$WaitSeconds = 43200,
    [int]$StartupSeconds = 120
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Invoke-DesktopCommand {
    param([string]$Executable, [string]$Command)
    $process = Start-Process -FilePath $Executable -ArgumentList @('--desktop-command', $Command) -PassThru -WindowStyle Hidden
    if (-not $process.WaitForExit(30000)) { throw 'Desktop control request timed out; update aborted.' }
    return $process.ExitCode
}

function Get-TargetProcesses {
    param([string]$Executable)
    return @(Get-Process -Name SplatReplay -ErrorAction SilentlyContinue | Where-Object { $_.Path -eq $Executable })
}

function Wait-DesktopState {
    param([string]$Executable, [int]$Expected, [int]$TimeoutSeconds)
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        if ((Invoke-DesktopCommand $Executable 'status') -eq $Expected) { return }
        if (@(Get-TargetProcesses $Executable).Count -eq 0) { throw 'Desktop exited before it became ready.' }
        Start-Sleep -Milliseconds 500
    } while ((Get-Date) -lt $deadline)
    throw 'Desktop startup timed out.'
}

function Invoke-ResidentUpdateCore {
    param([string]$Source, [string]$Destination, [int]$WaitLimit, [int]$StartupLimit)
    if ($WaitLimit -lt 1 -or $StartupLimit -lt 1) { throw 'Timeouts must be positive.' }
    $sourcePath = [IO.Path]::GetFullPath($Source).TrimEnd('\')
    $targetPath = [IO.Path]::GetFullPath($Destination).TrimEnd('\')
    if ($sourcePath -eq $targetPath -or $sourcePath.StartsWith($targetPath + '\', [StringComparison]::OrdinalIgnoreCase) -or $targetPath.StartsWith($sourcePath + '\', [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Source must be outside the destination.'
    }
    if ($targetPath -eq [IO.Path]::GetPathRoot($targetPath).TrimEnd('\')) { throw 'Drive root cannot be updated.' }
    $parts = @('SplatReplay.exe', '_internal', 'assets')
    foreach ($root in @($sourcePath, $targetPath)) {
        $marker = Join-Path $root 'assets\desktop-control.json'
        if (-not (Test-Path -LiteralPath $marker) -or (Get-Content -LiteralPath $marker -Raw | ConvertFrom-Json).version -ne 1) { throw 'This package does not support the resident update protocol.' }
    }
    foreach ($part in $parts) {
        if (-not (Test-Path -LiteralPath (Join-Path $sourcePath $part))) { throw "Missing update component: $part" }
    }
    $executable = Join-Path $targetPath 'SplatReplay.exe'
    if (-not (Test-Path -LiteralPath $executable)) { throw 'Install the desktop application before using resident update.' }
    # 参照先への再帰操作を避け、検証済み配置先の直下だけを差し替える。
    $checkedItems = @(Get-Item -LiteralPath $targetPath) + @(Get-Item -LiteralPath $sourcePath)
    foreach ($part in @('_internal', 'assets')) {
        foreach ($root in @($targetPath, $sourcePath)) {
            $partPath = Join-Path $root $part
            if (Test-Path -LiteralPath $partPath) { $checkedItems += @(Get-Item -LiteralPath $partPath) + @(Get-ChildItem -LiteralPath $partPath -Recurse -Force) }
        }
    }
    foreach ($item in $checkedItems) {
        if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Reparse points are not supported in the update destination.' }
    }
    $transaction = Join-Path $targetPath ('.splat-update-' + [guid]::NewGuid().ToString('N'))
    $candidate = Join-Path $transaction 'candidate'
    $backup = Join-Path $transaction 'previous'
    New-Item -ItemType Directory -Path $candidate, $backup | Out-Null
    foreach ($part in $parts) { Copy-Item -LiteralPath (Join-Path $sourcePath $part) -Destination $candidate -Recurse -ErrorAction Stop }
    $font = Join-Path $targetPath 'assets\thumbnail\ikamodoki1.ttf'
    if (Test-Path -LiteralPath $font) {
        $fontDir = Join-Path $candidate 'assets\thumbnail'
        New-Item -ItemType Directory -Path $fontDir -Force | Out-Null
        Copy-Item -LiteralPath $font -Destination $fontDir -Force
    }
    $oldProcesses = @(Get-TargetProcesses $executable)
    if ($oldProcesses.Count -gt 0) {
        if ((Invoke-DesktopCommand $executable 'update') -ne 0) { throw 'Could not reserve the update.' }
        Write-Host 'Switchのスリープと編集・アップロード完了を待っています。通知領域から取り消せます。'
        $deadline = (Get-Date).AddSeconds($WaitLimit)
        $nextStatusCheck = (Get-Date).AddSeconds(5)
        foreach ($process in $oldProcesses) {
            while (-not $process.WaitForExit(500)) {
                if ((Get-Date) -ge $nextStatusCheck) {
                    if ((Invoke-DesktopCommand $executable 'status') -eq 7) { throw 'Update was cancelled. No files were replaced.' }
                    $nextStatusCheck = (Get-Date).AddSeconds(5)
                }
                if ((Get-Date) -ge $deadline) {
                    $null = Invoke-DesktopCommand $executable 'cancel'
                    throw 'Update wait timed out. No files were replaced.'
                }
            }
            if ($process.ExitCode -ne 0) { throw 'Desktop did not exit normally. No files were replaced.' }
        }
        if (@(Get-TargetProcesses $executable).Count -gt 0) { throw 'Another desktop instance is still running.' }
    }
    $moved = @()
    $installed = @()
    $resumed = $false
    try {
        foreach ($part in $parts) {
            $target = Join-Path $targetPath $part
            if (Test-Path -LiteralPath $target) {
                Move-Item -LiteralPath $target -Destination (Join-Path $backup $part)
                $moved += $part
            }
            Move-Item -LiteralPath (Join-Path $candidate $part) -Destination $target
            $installed += $part
        }
        $null = Start-Process -FilePath $executable -ArgumentList @('--background', '--hold') -WorkingDirectory $targetPath -PassThru -WindowStyle Hidden
        Wait-DesktopState $executable 6 $StartupLimit
        if ((Invoke-DesktopCommand $executable 'resume') -ne 0) { throw 'Could not activate the updated desktop.' }
        # ここ以降は仕事が始まり得るため、自動的に旧版へ戻さない。
        $resumed = $true
        Wait-DesktopState $executable 0 $StartupLimit
        Write-Host "更新が完了しました。旧版本体: $backup"
    }
    catch {
        if ($resumed) { throw }
        $running = @(Get-TargetProcesses $executable)
        if ($running.Count -gt 0) {
            $null = Invoke-DesktopCommand $executable 'quit'
            foreach ($process in $running) {
                if (-not $process.WaitForExit(60000)) { throw 'Updated desktop could not stop. Backup retained; manual recovery required.' }
            }
        }
        foreach ($part in $installed) {
            $target = [IO.Path]::GetFullPath((Join-Path $targetPath $part))
            if (-not $target.StartsWith($targetPath + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Invalid rollback target.' }
            # パス・構成要素は上で検証済み。ユーザーデータは対象に含めない。
            Remove-Item -LiteralPath $target -Recurse -Force
        }
        foreach ($part in $moved) { Move-Item -LiteralPath (Join-Path $backup $part) -Destination (Join-Path $targetPath $part) }
        $null = Start-Process -FilePath $executable -ArgumentList @('--background', '--hold') -WorkingDirectory $targetPath -PassThru -WindowStyle Hidden
        Wait-DesktopState $executable 6 $StartupLimit
        $null = Invoke-DesktopCommand $executable 'resume'
        throw
    }
}

function Invoke-ResidentUpdate {
    param([string]$Source, [string]$Destination, [int]$WaitLimit, [int]$StartupLimit)
    $identity = [IO.Path]::GetFullPath((Join-Path $Destination 'SplatReplay.exe')).ToLowerInvariant() + [Security.Principal.WindowsIdentity]::GetCurrent().User.Value
    $sha = [Security.Cryptography.SHA256]::Create()
    try { $key = ([BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($identity))) -replace '-', '').ToLowerInvariant().Substring(0, 24) }
    finally { $sha.Dispose() }
    $mutex = [Threading.Mutex]::new($false, ('Local\SplatReplay-' + $key + '-updater'))
    $acquired = $false
    try {
        try { $acquired = $mutex.WaitOne(0) } catch [Threading.AbandonedMutexException] { $acquired = $true }
        if (-not $acquired) { throw 'Another update is already running.' }
        Invoke-ResidentUpdateCore $Source $Destination $WaitLimit $StartupLimit
    }
    finally {
        if ($acquired) { $mutex.ReleaseMutex() }
        $mutex.Dispose()
    }
}

if ($MyInvocation.InvocationName -ne '.') {
    Invoke-ResidentUpdate $SourceDir $DestinationDir $WaitSeconds $StartupSeconds
}
