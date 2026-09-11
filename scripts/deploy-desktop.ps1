[CmdletBinding()]
param(
    [Parameter()]
    [ValidateSet("Inspect", "Execute")]
    [string]$Mode = "Inspect",

    [Parameter()]
    [string]$RepoRoot = (Get-Location).Path,

    [Parameter()]
    [string]$EnvFile = "scripts/deploy-desktop.env",

    [Parameter()]
    [switch]$StopRunningApps
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function ConvertTo-NormalizedPath {
    param([Parameter(Mandatory = $true)][string]$Path)

    $fullPath = [System.IO.Path]::GetFullPath($Path)
    $separators = [char[]]@(
        [System.IO.Path]::DirectorySeparatorChar,
        [System.IO.Path]::AltDirectorySeparatorChar
    )
    return $fullPath.TrimEnd($separators)
}

function ConvertTo-Sha256Hex {
    param([Parameter(Mandatory = $true)][AllowEmptyString()][string]$Text)

    $bytes = [System.Text.Encoding]::UTF8.GetBytes($Text)
    $sha256 = [System.Security.Cryptography.SHA256]::Create()
    try {
        $hash = $sha256.ComputeHash($bytes)
    }
    finally {
        $sha256.Dispose()
    }

    return ([System.BitConverter]::ToString($hash) -replace "-", "").ToLowerInvariant()
}

function Get-Sha256FileHex {
    param([Parameter(Mandatory = $true)][string]$Path)

    $stream = [System.IO.File]::OpenRead($Path)
    $sha256 = [System.Security.Cryptography.SHA256]::Create()
    try {
        $hash = $sha256.ComputeHash($stream)
    }
    finally {
        $sha256.Dispose()
        $stream.Dispose()
    }

    return ([System.BitConverter]::ToString($hash) -replace "-", "").ToLowerInvariant()
}

function ConvertTo-Array {
    param([Parameter()][AllowNull()][object]$Value)

    if ($null -eq $Value) {
        return @()
    }

    return @($Value)
}

function ConvertTo-SerializableObject {
    param([Parameter()][AllowNull()][object]$Value)

    if ($null -eq $Value) {
        return $null
    }

    if ($Value -is [System.Collections.IDictionary]) {
        $converted = [ordered]@{}
        foreach ($key in $Value.Keys) {
            $converted[$key] = ConvertTo-SerializableObject -Value $Value[$key]
        }
        return [pscustomobject]$converted
    }

    if ($Value -is [System.Collections.IEnumerable] -and -not ($Value -is [string])) {
        $items = foreach ($item in $Value) {
            ConvertTo-SerializableObject -Value $item
        }
        return @($items)
    }

    return $Value
}

function Resolve-PathFromBase {
    param(
        [Parameter(Mandatory = $true)][string]$BaseDir,
        [Parameter(Mandatory = $true)][string]$Path
    )

    if ([System.IO.Path]::IsPathRooted($Path)) {
        return ConvertTo-NormalizedPath -Path $Path
    }

    return ConvertTo-NormalizedPath -Path (Join-Path $BaseDir $Path)
}

function Read-DeployEnvFile {
    param([Parameter(Mandatory = $true)][string]$Path)

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "Deploy env file not found: $Path"
    }

    $values = @{}
    foreach ($line in Get-Content -LiteralPath $Path -Encoding UTF8) {
        $trimmed = $line.Trim()
        if ([string]::IsNullOrWhiteSpace($trimmed) -or $trimmed.StartsWith("#")) {
            continue
        }

        if ($trimmed.StartsWith("export ")) {
            $trimmed = $trimmed.Substring("export ".Length).Trim()
        }

        $equalsIndex = $trimmed.IndexOf("=")
        if ($equalsIndex -le 0) {
            throw "Invalid env line in ${Path}: $line"
        }

        $name = $trimmed.Substring(0, $equalsIndex).Trim()
        $value = $trimmed.Substring($equalsIndex + 1).Trim()
        if ([string]::IsNullOrWhiteSpace($name)) {
            throw "Invalid empty env name in ${Path}: $line"
        }

        if (
            ($value.Length -ge 2) -and
            (($value.StartsWith('"') -and $value.EndsWith('"')) -or ($value.StartsWith("'") -and $value.EndsWith("'")))
        ) {
            $value = $value.Substring(1, $value.Length - 2)
        }

        $values[$name] = [System.Environment]::ExpandEnvironmentVariables($value)
    }

    return $values
}

function Get-DeployTargetFromEnvFile {
    param(
        [Parameter(Mandatory = $true)][string]$EnvFilePath,
        [Parameter(Mandatory = $true)][string]$RepoRootPath
    )

    $resolvedEnvFile = Resolve-PathFromBase -BaseDir $RepoRootPath -Path $EnvFilePath
    $values = Read-DeployEnvFile -Path $resolvedEnvFile
    $target = $values["SPLAT_REPLAY_DESKTOP_DEPLOY_DIR"]
    if ([string]::IsNullOrWhiteSpace($target)) {
        throw "SPLAT_REPLAY_DESKTOP_DEPLOY_DIR is required in $resolvedEnvFile."
    }

    return [ordered]@{
        envFile = $resolvedEnvFile
        deployDir = $target
    }
}

function Assert-DeployPath {
    param([Parameter(Mandatory = $true)][string]$DeployDir)

    $normalizedDeployDir = ConvertTo-NormalizedPath -Path $DeployDir
    if (-not (Test-Path -LiteralPath $normalizedDeployDir -PathType Container)) {
        throw "Deploy target does not exist: $normalizedDeployDir"
    }

    $driveRoot = ConvertTo-NormalizedPath -Path ([System.IO.Path]::GetPathRoot($normalizedDeployDir))
    if ($normalizedDeployDir -ieq $driveRoot) {
        throw "Deploy target must not be a drive root: $normalizedDeployDir"
    }

    $desktopRoot = ConvertTo-NormalizedPath -Path (Join-Path $env:USERPROFILE "Desktop")
    if ($normalizedDeployDir -ieq $desktopRoot) {
        throw "Deploy target must not be the Desktop root itself: $normalizedDeployDir"
    }

    return $normalizedDeployDir
}

function Invoke-GitText {
    param(
        [Parameter(Mandatory = $true)][string]$WorkingTree,
        [Parameter(Mandatory = $true)][string[]]$Arguments
    )

    $stderrFile = [System.IO.Path]::GetTempFileName()
    $previousErrorActionPreference = $ErrorActionPreference
    $previousConsoleOutputEncoding = [Console]::OutputEncoding
    try {
        $ErrorActionPreference = "Continue"
        [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
        $output = & git -C $WorkingTree @Arguments 2> $stderrFile
        $exitCode = $LASTEXITCODE
        $stderr = Get-Content -LiteralPath $stderrFile -Raw -Encoding UTF8
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
        [Console]::OutputEncoding = $previousConsoleOutputEncoding
        Remove-Item -LiteralPath $stderrFile -Force -ErrorAction SilentlyContinue
    }

    $outputText = if ($null -eq $output) { "" } else { [string]::Join("`n", @($output)) }
    if ($exitCode -ne 0) {
        $messages = @()
        if (-not [string]::IsNullOrWhiteSpace($outputText)) {
            $messages += $outputText
        }
        if (-not [string]::IsNullOrWhiteSpace($stderr)) {
            $messages += $stderr.TrimEnd()
        }

        $message = if ($messages.Count -gt 0) { [string]::Join("`n", $messages) } else { "git command failed." }
        throw "git $($Arguments -join ' ') failed: $message"
    }

    return $outputText
}

function Get-UntrackedEntries {
    param([Parameter(Mandatory = $true)][string]$WorkingTree)

    $raw = Invoke-GitText -WorkingTree $WorkingTree -Arguments @(
        "-c",
        "core.quotePath=false",
        "ls-files",
        "--others",
        "--exclude-standard"
    )
    if ([string]::IsNullOrWhiteSpace($raw)) {
        return @()
    }

    $paths = $raw -split "`r?`n" | Where-Object { $_ -and $_.Trim().Length -gt 0 }
    $entries = foreach ($relativePath in $paths) {
        $absolutePath = Join-Path $WorkingTree $relativePath
        if (-not (Test-Path -LiteralPath $absolutePath -PathType Leaf)) {
            [ordered]@{
                path = $relativePath
                missing = $true
            }
            continue
        }

        [ordered]@{
            path = $relativePath
            sha256 = Get-Sha256FileHex -Path $absolutePath
        }
    }

    return (ConvertTo-Array -Value $entries)
}

function Get-SourceState {
    param([Parameter(Mandatory = $true)][string]$WorkingTree)

    $head = Invoke-GitText -WorkingTree $WorkingTree -Arguments @("rev-parse", "HEAD")
    $trackedDiff = Invoke-GitText -WorkingTree $WorkingTree -Arguments @("--no-pager", "diff", "--binary", "HEAD", "--")
    $untrackedEntries = Get-UntrackedEntries -WorkingTree $WorkingTree

    $payload = [ordered]@{
        repoRoot = $WorkingTree
        head = $head.Trim()
        trackedDiffSha256 = ConvertTo-Sha256Hex -Text $trackedDiff
        untracked = $untrackedEntries
    }

    $fingerprint = ConvertTo-Sha256Hex -Text ($payload | ConvertTo-Json -Depth 8 -Compress)
    return [ordered]@{
        head = $payload.head
        trackedDiffSha256 = $payload.trackedDiffSha256
        untracked = $untrackedEntries
        fingerprint = $fingerprint
    }
}

function Get-BlockingProcesses {
    $running = Get-Process -Name @("SplatReplay", "obs64") -ErrorAction SilentlyContinue |
        Sort-Object ProcessName, Id

    $entries = foreach ($process in $running) {
        $path = $null
        try {
            $path = $process.Path
        }
        catch {
            $path = $null
        }

        [ordered]@{
            processName = $process.ProcessName
            id = $process.Id
            mainWindowTitle = $process.MainWindowTitle
            path = $path
        }
    }

    return (ConvertTo-Array -Value $entries)
}

function Stop-BlockingProcesses {
    param([Parameter(Mandatory = $true)][object[]]$BlockingProcesses)

    $actions = @()

    foreach ($entry in $BlockingProcesses) {
        $process = Get-Process -Id $entry.id -ErrorAction SilentlyContinue
        if ($null -eq $process) {
            $actions += [ordered]@{
                processName = $entry.processName
                id = $entry.id
                action = "already-exited"
            }
            continue
        }

        $graceful = $false
        if ($process.MainWindowHandle -ne 0) {
            try {
                $graceful = $process.CloseMainWindow()
            }
            catch {
                $graceful = $false
            }
        }

        if ($graceful) {
            try {
                Wait-Process -Id $process.Id -Timeout 15 -ErrorAction Stop
                $actions += [ordered]@{
                    processName = $process.ProcessName
                    id = $process.Id
                    action = "closed-main-window"
                }
                continue
            }
            catch {
                # Fall through to forced stop.
            }
        }

        Stop-Process -Id $process.Id -Force -ErrorAction Stop
        Wait-Process -Id $process.Id -Timeout 15 -ErrorAction Stop
        $actions += [ordered]@{
            processName = $process.ProcessName
            id = $process.Id
            action = if ($graceful) { "force-stopped-after-timeout" } else { "force-stopped" }
        }
    }

    return (ConvertTo-Array -Value $actions)
}

function Invoke-TaskBuild {
    param([Parameter(Mandatory = $true)][string]$WorkingTree)

    Push-Location $WorkingTree
    try {
        & task.exe build
        if ($LASTEXITCODE -ne 0) {
            throw "task.exe build failed with exit code $LASTEXITCODE."
        }
    }
    finally {
        Pop-Location
    }
}

function Invoke-DesktopDeployCopy {
    param(
        [Parameter(Mandatory = $true)][string]$SourceDir,
        [Parameter(Mandatory = $true)][string]$DestinationDir
    )

    if (-not (Test-Path -LiteralPath $SourceDir -PathType Container)) {
        throw "Deploy source directory not found: $SourceDir"
    }

    if (-not (Test-Path -LiteralPath $DestinationDir -PathType Container)) {
        throw "Deploy target does not exist: $DestinationDir"
    }

    $sourceExe = Join-Path $SourceDir "SplatReplay.exe"
    $sourceInternalDir = Join-Path $SourceDir "_internal"
    $sourceAssetsDir = Join-Path $SourceDir "assets"
    $targetInternalDir = Join-Path $DestinationDir "_internal"
    $targetAssetsDir = Join-Path $DestinationDir "assets"

    if (-not (Test-Path -LiteralPath $sourceExe -PathType Leaf)) {
        throw "Deploy executable not found: $sourceExe"
    }

    if (-not (Test-Path -LiteralPath $sourceInternalDir -PathType Container)) {
        throw "Deploy internal directory not found: $sourceInternalDir"
    }

    if (-not (Test-Path -LiteralPath $sourceAssetsDir -PathType Container)) {
        throw "Deploy assets directory not found: $sourceAssetsDir"
    }

    Copy-Item -LiteralPath $sourceExe -Destination $DestinationDir -Force -ErrorAction Stop

    if (Test-Path -LiteralPath $targetInternalDir) {
        Remove-Item -LiteralPath $targetInternalDir -Recurse -Force -ErrorAction Stop
    }

    Copy-Item -LiteralPath $sourceInternalDir -Destination $DestinationDir -Recurse -Force -ErrorAction Stop

    if (Test-Path -LiteralPath $targetAssetsDir) {
        Remove-Item -LiteralPath $targetAssetsDir -Recurse -Force -ErrorAction Stop
    }

    Copy-Item -LiteralPath $sourceAssetsDir -Destination $DestinationDir -Recurse -Force -ErrorAction Stop

    return [ordered]@{
        copiedExe = "SplatReplay.exe"
        replacedInternal = "_internal"
        replacedAssets = "assets"
    }
}

function Write-ResultLine {
    param([Parameter(Mandatory = $true)][object]$Result)

    $serializable = ConvertTo-SerializableObject -Value $Result
    $json = $serializable | ConvertTo-Json -Depth 10 -Compress
    Write-Output ("RESULT_JSON: " + $json)
}

$result = [ordered]@{}

try {
    $normalizedRepoRoot = ConvertTo-NormalizedPath -Path $RepoRoot
    $deployConfig = Get-DeployTargetFromEnvFile -EnvFilePath $EnvFile -RepoRootPath $normalizedRepoRoot
    $deployDir = Assert-DeployPath -DeployDir $deployConfig.deployDir
    $stateDir = Join-Path (Join-Path $normalizedRepoRoot ".task") "desktop-deploy"
    $distDir = Join-Path (Join-Path $normalizedRepoRoot "dist") "SplatReplay"
    $distExe = Join-Path $distDir "SplatReplay.exe"
    $repoKey = ConvertTo-Sha256Hex -Text $normalizedRepoRoot.ToLowerInvariant()
    $stateFile = Join-Path $stateDir "$repoKey.json"
    $sourceState = Get-SourceState -WorkingTree $normalizedRepoRoot
    $blockingProcesses = @(Get-BlockingProcesses)
    $previousState = $null

    if (Test-Path -LiteralPath $stateFile -PathType Leaf) {
        $previousState = Get-Content -LiteralPath $stateFile -Raw -Encoding UTF8 | ConvertFrom-Json
    }

    $buildReasons = @()
    if (-not (Test-Path -LiteralPath $distExe -PathType Leaf)) {
        $buildReasons += "dist-exe-missing"
    }
    if ($null -eq $previousState) {
        $buildReasons += "no-prior-build-state"
    }
    elseif ($previousState.repoRoot -ne $normalizedRepoRoot) {
        $buildReasons += "state-repo-mismatch"
    }
    elseif ($previousState.fingerprint -ne $sourceState.fingerprint) {
        $buildReasons += "source-changed"
    }

    $buildRequired = $buildReasons.Count -gt 0

    $result = [ordered]@{
        mode = $Mode
        success = $true
        repoRoot = $normalizedRepoRoot
        envFile = $deployConfig.envFile
        distDir = $distDir
        distExe = $distExe
        desktopDeployDir = $deployDir
        stateFile = $stateFile
        head = $sourceState.head
        fingerprint = $sourceState.fingerprint
        buildRequired = $buildRequired
        buildReasons = [object[]](ConvertTo-Array -Value $buildReasons)
        buildExecuted = $false
        buildSkipped = $false
        blockingProcesses = [object[]](ConvertTo-Array -Value $blockingProcesses)
        closedProcesses = [object[]]@()
        deployExecuted = $false
        deployCopyActions = [object[]]@()
        requiresUserConfirmation = (@($blockingProcesses).Count -gt 0 -and -not $StopRunningApps.IsPresent)
    }

    if ($Mode -eq "Inspect") {
        Write-ResultLine -Result $result
        exit 0
    }

    if (@($blockingProcesses).Count -gt 0 -and -not $StopRunningApps.IsPresent) {
        throw "Blocking processes are running. Re-run deploy:stop-running-apps only after confirming they can be closed."
    }

    if (@($blockingProcesses).Count -gt 0 -and $StopRunningApps.IsPresent) {
        $result.closedProcesses = [object[]](Stop-BlockingProcesses -BlockingProcesses $blockingProcesses)
        Start-Sleep -Seconds 1
        $remainingProcesses = @(Get-BlockingProcesses)
        if (@($remainingProcesses).Count -gt 0) {
            $result.blockingProcesses = [object[]]$remainingProcesses
            throw "Some blocking processes are still running after stop attempts."
        }
        $result.blockingProcesses = [object[]]@()
        $result.requiresUserConfirmation = $false
    }

    if ($buildRequired) {
        Invoke-TaskBuild -WorkingTree $normalizedRepoRoot
        $result.buildExecuted = $true
    }
    else {
        $result.buildSkipped = $true
    }

    if (-not (Test-Path -LiteralPath $distExe -PathType Leaf)) {
        throw "Build output not found after build step: $distExe"
    }

    $deployActions = Invoke-DesktopDeployCopy -SourceDir $distDir -DestinationDir $deployDir
    $result.deployExecuted = $true
    $result.deployCopyActions = [object[]](ConvertTo-Array -Value $deployActions)

    New-Item -ItemType Directory -Force -Path $stateDir | Out-Null
    $state = [ordered]@{
        tool = "task-desktop-deploy"
        version = 1
        repoRoot = $normalizedRepoRoot
        envFile = $deployConfig.envFile
        fingerprint = $sourceState.fingerprint
        head = $sourceState.head
        builtAtUtc = (Get-Date).ToUniversalTime().ToString("o")
        desktopDeployDir = $deployDir
        distExe = $distExe
        distExeLastWriteTimeUtc = (Get-Item -LiteralPath $distExe).LastWriteTimeUtc.ToString("o")
    }
    $state | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $stateFile -Encoding UTF8

    Write-ResultLine -Result $result
    exit 0
}
catch {
    if ($result.Count -eq 0) {
        $result = [ordered]@{
            mode = $Mode
            success = $false
            repoRoot = $RepoRoot
            envFile = $EnvFile
        }
    }
    else {
        $result.success = $false
    }

    $result.error = $_.Exception.Message
    Write-ResultLine -Result $result
    exit 1
}
