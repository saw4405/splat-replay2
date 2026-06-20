$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$tempRoot = Join-Path $repoRoot ".tmp"
New-Item -ItemType Directory -Force -Path $tempRoot | Out-Null

$uvCacheRoot = Join-Path $repoRoot ".uv-cache"
$uvPythonRoot = Join-Path $repoRoot ".uv-python"
New-Item -ItemType Directory -Force -Path $uvCacheRoot, $uvPythonRoot | Out-Null

if ([string]::IsNullOrWhiteSpace($env:UV_CACHE_DIR)) {
    $env:UV_CACHE_DIR = $uvCacheRoot
}

if ([string]::IsNullOrWhiteSpace($env:UV_PYTHON_INSTALL_DIR)) {
    $env:UV_PYTHON_INSTALL_DIR = $uvPythonRoot
}

$env:TMP = $tempRoot
$env:TEMP = $tempRoot
$env:TMPDIR = $tempRoot

$baseTemp = Join-Path $tempRoot ("pytest-basetemp-{0}" -f $PID)

& uv run pytest "--basetemp=$baseTemp" -p no:cacheprovider @args
$exitCode = $LASTEXITCODE

if ($exitCode -eq 5 -and $env:PYTEST_ALLOW_NO_TESTS -eq "1") {
    exit 0
}

exit $exitCode
