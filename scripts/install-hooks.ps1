param(
    [string]$SkipHooks = ""
)

$ErrorActionPreference = "Stop"

if ($SkipHooks -eq "1") {
    Write-Warning "SKIP_HOOKS=1: Git hooks setup was skipped. Re-enable hooks before using the normal commit/push flow."
    exit 0
}

$repoRoot = (git rev-parse --show-toplevel).Trim()
if (-not $repoRoot) {
    Write-Error "must run inside a git repository"
    exit 1
}

Set-Location $repoRoot

git config extensions.worktreeConfig true
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

$sharedHooksPath = git config --local --get core.hooksPath 2>$null
$sharedHooksExit = $LASTEXITCODE
if ($sharedHooksExit -eq 0 -and $sharedHooksPath.Trim().Replace("\", "/") -eq ".githooks") {
    git config --local --unset core.hooksPath
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}

git config --worktree core.hooksPath .githooks
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

$python = Join-Path $repoRoot "backend/.venv/Scripts/python.exe"
if (-not (Test-Path $python)) {
    Write-Error "backend venv Python was not found: $python"
    exit 1
}

$env:PRE_COMMIT_HOME = Join-Path $repoRoot ".pre-commit-cache"
$env:VIRTUALENV_OVERRIDE_APP_DATA = Join-Path $env:PRE_COMMIT_HOME "virtualenv-app-data"
New-Item -ItemType Directory -Force -Path $env:PRE_COMMIT_HOME, $env:VIRTUALENV_OVERRIDE_APP_DATA | Out-Null

& $python -m pre_commit install-hooks --config .pre-commit-config.yaml
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
